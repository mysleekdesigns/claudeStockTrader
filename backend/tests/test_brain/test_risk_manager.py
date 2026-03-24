"""Tests for the risk manager — circuit breaker and position sizing."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from backend.brain.risk_manager import RiskManager
from backend.database.models import RiskState, SignalStatus


pytestmark = pytest.mark.asyncio


class TestCheckRiskState:
    async def test_tradeable_with_clean_state(self, session: AsyncSession, clean_risk_state):
        mgr = RiskManager(session)
        is_tradeable, status = await mgr.check_risk_state()
        assert is_tradeable is True
        assert "OK" in status

    async def test_shutdown_on_daily_loss_cap(self, session: AsyncSession):
        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        state = RiskState(
            date=today, daily_loss_pct=0.025, consecutive_stops=0, is_shutdown=False
        )
        session.add(state)
        await session.commit()

        mgr = RiskManager(session)
        is_tradeable, status = await mgr.check_risk_state()
        assert is_tradeable is False
        assert "SHUTDOWN" in status

    async def test_shutdown_on_consecutive_stops(self, session: AsyncSession):
        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        state = RiskState(
            date=today, daily_loss_pct=0.005, consecutive_stops=8, is_shutdown=False
        )
        session.add(state)
        await session.commit()

        mgr = RiskManager(session)
        is_tradeable, status = await mgr.check_risk_state()
        assert is_tradeable is False
        assert "consecutive" in status.lower() or "SHUTDOWN" in status

    async def test_exactly_8_stops_triggers_circuit_breaker(self, session: AsyncSession, risk_state_near_limit):
        """7 consecutive stops + 1 more loss = 8 = circuit breaker."""
        mgr = RiskManager(session)
        # Record one more loss to hit 8
        await mgr.record_signal_result(SignalStatus.LOST, -5.0, 100000.0)

        # Refresh from DB
        is_tradeable, status = await mgr.check_risk_state()
        assert is_tradeable is False

    async def test_win_resets_consecutive_stops(self, session: AsyncSession, risk_state_near_limit):
        mgr = RiskManager(session)
        await mgr.record_signal_result(SignalStatus.WON, 10.0, 100000.0)

        is_tradeable, status = await mgr.check_risk_state()
        assert is_tradeable is True
        assert "OK" in status

    async def test_active_shutdown_with_future_expiry(self, session: AsyncSession):
        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        state = RiskState(
            date=today,
            daily_loss_pct=0.005,
            consecutive_stops=8,
            is_shutdown=True,
            shutdown_until=datetime.now(timezone.utc) + timedelta(hours=12),
        )
        session.add(state)
        await session.commit()

        mgr = RiskManager(session)
        is_tradeable, status = await mgr.check_risk_state()
        assert is_tradeable is False
        assert "SHUTDOWN" in status


class TestPositionSizing:
    async def test_basic_position_size(self, session: AsyncSession, clean_risk_state):
        mgr = RiskManager(session)
        size = await mgr.calculate_position_size(
            account_equity=100000.0,
            current_atr=15.0,
            avg_atr_20=15.0,
            pip_risk=20.0,
        )
        assert size > 0
        # Max 1% risk: 100000 * 0.01 / 20 = 50
        assert size <= 50.0

    async def test_zero_pip_risk_returns_zero(self, session: AsyncSession, clean_risk_state):
        mgr = RiskManager(session)
        size = await mgr.calculate_position_size(
            account_equity=100000.0,
            current_atr=15.0,
            avg_atr_20=15.0,
            pip_risk=0.0,
        )
        assert size == 0.0

    async def test_high_volatility_reduces_size(self, session: AsyncSession, clean_risk_state):
        mgr = RiskManager(session)
        # Normal volatility
        normal = await mgr.calculate_position_size(
            account_equity=100000.0, current_atr=15.0, avg_atr_20=15.0, pip_risk=20.0
        )
        # High volatility (ATR > 2x average)
        high = await mgr.calculate_position_size(
            account_equity=100000.0, current_atr=35.0, avg_atr_20=15.0, pip_risk=20.0
        )
        assert high < normal

    async def test_never_exceeds_1_percent_risk(self, session: AsyncSession, clean_risk_state):
        mgr = RiskManager(session)
        size = await mgr.calculate_position_size(
            account_equity=100000.0,
            current_atr=5.0,
            avg_atr_20=5.0,
            pip_risk=1.0,  # Very small pip risk => large position
        )
        actual_risk = size * 1.0
        assert actual_risk <= 100000.0 * 0.01 + 0.01  # 1% + epsilon


class TestRecordSignalResult:
    async def test_loss_increments_consecutive(self, session: AsyncSession, clean_risk_state):
        mgr = RiskManager(session)
        await mgr.record_signal_result(SignalStatus.LOST, -10.0, 100000.0)

        is_tradeable, status = await mgr.check_risk_state()
        assert is_tradeable is True  # Only 1 loss
        assert "consecutive_stops=1" in status

    async def test_win_after_losses_resets(self, session: AsyncSession, clean_risk_state):
        mgr = RiskManager(session)
        # Record 3 losses
        for _ in range(3):
            await mgr.record_signal_result(SignalStatus.LOST, -5.0, 100000.0)
        # Then a win
        await mgr.record_signal_result(SignalStatus.WON, 10.0, 100000.0)

        is_tradeable, status = await mgr.check_risk_state()
        assert is_tradeable is True
        assert "consecutive_stops=0" in status
