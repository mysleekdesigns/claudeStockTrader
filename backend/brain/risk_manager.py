"""Risk manager — enforces hard risk limits and circuit breaker logic."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.database.models import SignalStatus
from backend.database.repositories.risk import RiskRepository

logger = logging.getLogger(__name__)


class RiskManager:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._risk_repo = RiskRepository(session)

    async def check_risk_state(self) -> tuple[bool, str]:
        """Check current risk state. Returns (is_tradeable, status_description).

        Enforces:
        - 2% daily loss cap -> shutdown
        - 8 consecutive stop losses -> 24h shutdown
        """
        state = await self._risk_repo.get_or_create_today()

        # Check if already in shutdown and still within shutdown period
        if state.is_shutdown:
            if state.shutdown_until and datetime.now(timezone.utc) < state.shutdown_until:
                remaining = state.shutdown_until - datetime.now(timezone.utc)
                msg = f"SHUTDOWN: circuit breaker active, {remaining.seconds // 3600}h {(remaining.seconds % 3600) // 60}m remaining"
                logger.warning(msg)
                return False, msg

            # Daily loss shutdown (resets on new day — already a new day's record)
            if state.shutdown_until is None and state.daily_loss_pct >= settings.max_daily_loss:
                msg = f"SHUTDOWN: daily loss cap {state.daily_loss_pct:.2%} >= {settings.max_daily_loss:.2%}"
                logger.warning(msg)
                return False, msg

            # Shutdown period expired — auto-reset
            await self._risk_repo.reset_shutdown(state.id)
            logger.info("Circuit breaker reset: shutdown period expired")

        # Check daily loss cap
        if state.daily_loss_pct >= settings.max_daily_loss:
            await self._risk_repo.set_shutdown(state.id, shutdown_until=None)
            msg = f"SHUTDOWN TRIGGERED: daily loss {state.daily_loss_pct:.2%} hit {settings.max_daily_loss:.2%} cap"
            logger.warning(msg)
            return False, msg

        # Check consecutive stop losses
        if state.consecutive_stops >= settings.consecutive_sl_limit:
            shutdown_until = datetime.now(timezone.utc) + timedelta(hours=24)
            await self._risk_repo.set_shutdown(state.id, shutdown_until=shutdown_until)
            msg = f"SHUTDOWN TRIGGERED: {state.consecutive_stops} consecutive stops hit limit of {settings.consecutive_sl_limit}"
            logger.warning(msg)
            return False, msg

        status = f"OK: daily_loss={state.daily_loss_pct:.2%}, consecutive_stops={state.consecutive_stops}"
        return True, status

    async def calculate_position_size(
        self,
        account_equity: float,
        current_atr: float,
        avg_atr_20: float,
        pip_risk: float,
    ) -> float:
        """Calculate position size using ATR-based sizing with volatility scaling.

        Formula: (account_equity * max_risk_per_trade) / pip_risk * volatility_scale
        Volatility scaling: reduce when ATR > 2x 20-period average.
        Never exceed 1% risk per trade.
        """
        if pip_risk <= 0:
            return 0.0

        # Volatility scaling factor
        volatility_scale = 1.0
        if avg_atr_20 > 0 and current_atr > 2.0 * avg_atr_20:
            volatility_scale = avg_atr_20 / current_atr  # Reduce proportionally

        risk_amount = account_equity * settings.max_risk_per_trade
        position_size = (risk_amount / pip_risk) * volatility_scale

        # Hard cap: never risk more than 1%
        max_risk = account_equity * 0.01
        if position_size * pip_risk > max_risk:
            position_size = max_risk / pip_risk

        return max(0.0, position_size)

    async def record_signal_result(
        self,
        status: SignalStatus,
        pips_result: float,
        account_equity: float,
    ) -> None:
        """Update risk state after a signal resolves.

        Updates consecutive_stops counter and daily_loss_pct.
        """
        state = await self._risk_repo.get_or_create_today()

        if status == SignalStatus.LOST:
            new_consecutive = state.consecutive_stops + 1
            loss_pct = abs(pips_result) / account_equity if account_equity > 0 else 0.0
            new_daily_loss = state.daily_loss_pct + loss_pct

            await self._risk_repo.update_state(
                state.id,
                consecutive_stops=new_consecutive,
                daily_loss_pct=new_daily_loss,
            )
            logger.info(
                "Signal LOST recorded: consecutive_stops=%d, daily_loss=%.4f",
                new_consecutive,
                new_daily_loss,
            )
        elif status == SignalStatus.WON:
            # Reset consecutive stops on a win
            if state.consecutive_stops > 0:
                await self._risk_repo.update_state(state.id, consecutive_stops=0)
                logger.info("Signal WON: consecutive stops reset to 0")

    async def reset_circuit_breaker(self) -> None:
        """Hourly check to reset circuit breaker if shutdown period has expired.

        - Consecutive SL shutdowns: reset after 24h
        - Daily loss shutdowns: reset on new UTC day
        """
        state = await self._risk_repo.get_current()
        if state is None or not state.is_shutdown:
            return

        now = datetime.now(timezone.utc)

        # Timed shutdown (consecutive SLs) — check if period expired
        if state.shutdown_until and now >= state.shutdown_until:
            await self._risk_repo.reset_shutdown(state.id)
            logger.info("Circuit breaker reset: 24h shutdown period expired")
            return

        # Daily loss shutdown — check if we're on a new UTC day
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        if state.date < today_start:
            # New day — the get_or_create_today will create a fresh record
            # Just reset the old one
            await self._risk_repo.reset_shutdown(state.id)
            logger.info("Circuit breaker reset: new UTC day")
