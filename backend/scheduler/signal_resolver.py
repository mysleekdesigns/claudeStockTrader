"""Signal Resolution — runs every 5 minutes.

Checks pending/active signals against current price data.
- Won: price hit take_profit before stop_loss
- Lost: price hit stop_loss first
- Expired: neither hit within TTL (default 48h)

Updates strategy_performance metrics after each resolution.
Publishes status changes to Redis pub/sub.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import Candle, Signal, SignalDirection, SignalStatus, Timeframe
from backend.database.repositories.candles import CandleRepository
from backend.database.repositories.performance import PerformanceRepository
from backend.database.repositories.signals import SignalRepository

logger = logging.getLogger(__name__)

SIGNAL_TTL_HOURS = 48
REDIS_CHANNEL = "signals:XAU/USD"
SYMBOL = "XAU/USD"
PERFORMANCE_WINDOWS = [7, 30, 90]


class SignalResolver:
    def __init__(
        self,
        session: AsyncSession,
        redis_client: aioredis.Redis,
        ttl_hours: int = SIGNAL_TTL_HOURS,
    ):
        self.signal_repo = SignalRepository(session)
        self.candle_repo = CandleRepository(session)
        self.perf_repo = PerformanceRepository(session)
        self.redis = redis_client
        self.session = session
        self.ttl_hours = ttl_hours

    async def run(self) -> int:
        """Resolve all pending/active signals. Returns count of resolved signals."""
        signals = await self.signal_repo.get_pending_and_active()
        if not signals:
            return 0

        resolved_count = 0
        now = datetime.now(timezone.utc)

        for signal in signals:
            result = await self._check_signal(signal, now)
            if result is not None:
                status, pips = result
                await self.signal_repo.resolve(signal.id, status, pips)
                await self._publish_resolution(signal, status, pips)
                resolved_count += 1
                logger.info(
                    "Resolved signal %d (%s): %s, pips=%.2f",
                    signal.id,
                    signal.strategy_name,
                    status.value,
                    pips,
                )

        if resolved_count > 0:
            await self._update_performance_metrics()

        return resolved_count

    async def _check_signal(
        self, signal: Signal, now: datetime
    ) -> tuple[SignalStatus, float] | None:
        """Check a single signal against price data.

        Returns (status, pips_result) if resolved, None if still active.
        """
        created_at = signal.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)

        # Check expiry first
        expiry = created_at + timedelta(hours=self.ttl_hours)
        if now >= expiry:
            pips = self._calc_pips(signal, float(signal.entry_price))
            return SignalStatus.EXPIRED, pips

        # Get candles since signal creation (use 15m for granularity)
        candles = await self.candle_repo.get_range(
            symbol=SYMBOL,
            timeframe=Timeframe.M15,
            start=created_at,
            limit=2000,
        )

        if not candles:
            return None

        # Sort by timestamp ascending for chronological check
        candles_sorted = sorted(candles, key=lambda c: c.timestamp)

        for candle in candles_sorted:
            hit_tp = self._candle_hits_tp(signal, candle)
            hit_sl = self._candle_hits_sl(signal, candle)

            if hit_tp and hit_sl:
                # Both hit in same candle — use open direction to determine which hit first
                # If open is closer to SL, SL hit first; if closer to TP, TP hit first
                if signal.direction == SignalDirection.LONG:
                    # Long: SL below entry, TP above
                    if candle.low <= signal.stop_loss:
                        return SignalStatus.LOST, self._calc_pips(signal, signal.stop_loss)
                    return SignalStatus.WON, self._calc_pips(signal, signal.take_profit)
                else:
                    # Short: SL above entry, TP below
                    if candle.high >= signal.stop_loss:
                        return SignalStatus.LOST, self._calc_pips(signal, signal.stop_loss)
                    return SignalStatus.WON, self._calc_pips(signal, signal.take_profit)

            if hit_tp:
                return SignalStatus.WON, self._calc_pips(signal, signal.take_profit)
            if hit_sl:
                return SignalStatus.LOST, self._calc_pips(signal, signal.stop_loss)

        return None

    def _candle_hits_tp(self, signal: Signal, candle: Candle) -> bool:
        if signal.direction == SignalDirection.LONG:
            return candle.high >= signal.take_profit
        else:
            return candle.low <= signal.take_profit

    def _candle_hits_sl(self, signal: Signal, candle: Candle) -> bool:
        if signal.direction == SignalDirection.LONG:
            return candle.low <= signal.stop_loss
        else:
            return candle.high >= signal.stop_loss

    def _calc_pips(self, signal: Signal, exit_price: float) -> float:
        """Calculate pips result. For XAU/USD, 1 pip = 0.1."""
        pip_size = 0.1
        if signal.direction == SignalDirection.LONG:
            return (exit_price - signal.entry_price) / pip_size
        else:
            return (signal.entry_price - exit_price) / pip_size

    async def _publish_resolution(
        self, signal: Signal, status: SignalStatus, pips: float
    ) -> None:
        payload = json.dumps(
            {
                "event": "signal_resolved",
                "signal_id": signal.id,
                "strategy_name": signal.strategy_name,
                "direction": signal.direction.value,
                "status": status.value,
                "pips_result": pips,
                "entry_price": signal.entry_price,
                "stop_loss": signal.stop_loss,
                "take_profit": signal.take_profit,
            }
        )
        await self.redis.publish(REDIS_CHANNEL, payload)

    async def _update_performance_metrics(self) -> None:
        """Recalculate performance metrics for all strategies across time windows."""
        # Get all resolved signals
        all_signals = await self.signal_repo.list_signals(limit=10000)
        resolved = [
            s
            for s in all_signals
            if s.status in (SignalStatus.WON, SignalStatus.LOST, SignalStatus.EXPIRED)
        ]

        if not resolved:
            return

        now = datetime.now(timezone.utc)

        # Group by strategy
        strategies: dict[str, list[Signal]] = {}
        for s in resolved:
            strategies.setdefault(s.strategy_name, []).append(s)

        for strategy_name, signals in strategies.items():
            for window_days in PERFORMANCE_WINDOWS:
                cutoff = now - timedelta(days=window_days)
                window_signals = [
                    s
                    for s in signals
                    if s.resolved_at and s.resolved_at.replace(tzinfo=timezone.utc) >= cutoff
                ]
                if not window_signals:
                    continue

                total = len(window_signals)
                wins = sum(1 for s in window_signals if s.status == SignalStatus.WON)
                win_rate = wins / total if total > 0 else 0.0

                # Average risk/reward
                rr_values = []
                for s in window_signals:
                    risk = abs(s.entry_price - s.stop_loss)
                    reward = abs(s.take_profit - s.entry_price)
                    if risk > 0:
                        rr_values.append(reward / risk)
                avg_rr = sum(rr_values) / len(rr_values) if rr_values else 0.0

                # Sharpe ratio approximation from pips results
                pips_list = [s.pips_result or 0.0 for s in window_signals]
                if len(pips_list) > 1:
                    mean_pips = sum(pips_list) / len(pips_list)
                    std_pips = (
                        sum((p - mean_pips) ** 2 for p in pips_list) / (len(pips_list) - 1)
                    ) ** 0.5
                    sharpe = mean_pips / std_pips if std_pips > 0 else 0.0
                else:
                    sharpe = 0.0

                # Max drawdown from cumulative pips
                cumulative = 0.0
                peak = 0.0
                max_dd = 0.0
                for p in pips_list:
                    cumulative += p
                    if cumulative > peak:
                        peak = cumulative
                    dd = (peak - cumulative) / abs(peak) if peak > 0 else 0.0
                    if dd > max_dd:
                        max_dd = dd

                await self.perf_repo.upsert(
                    {
                        "strategy_name": strategy_name,
                        "window_days": window_days,
                        "win_rate": win_rate,
                        "avg_rr": avg_rr,
                        "total_signals": total,
                        "sharpe_ratio": sharpe,
                        "max_drawdown": max_dd,
                    }
                )
