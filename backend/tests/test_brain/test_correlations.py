"""Tests for correlation analyzer."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from backend.brain.correlations import CorrelationAnalyzer, CorrelationSummary
from backend.database.models import CorrelationData


@pytest_asyncio.fixture
async def populated_correlation_data(session: AsyncSession):
    """Insert 30 data points for DXY, US10Y, and XAU/USD."""
    now = datetime.now(timezone.utc)
    rows = []
    for i in range(30):
        ts = now - timedelta(hours=30 - i)
        # DXY trending down (104 -> ~101), gold should be bullish
        rows.append(CorrelationData(asset="DXY", price=104.0 - i * 0.1, timestamp=ts))
        # US10Y trending down (4.5 -> ~4.2)
        rows.append(CorrelationData(asset="US10Y", price=4.5 - i * 0.01, timestamp=ts))
        # Gold trending up
        rows.append(CorrelationData(asset="XAU/USD", price=2300.0 + i * 5.0, timestamp=ts))

    for row in rows:
        session.add(row)
    await session.commit()
    return rows


class TestCorrelationAnalyzer:
    @pytest.mark.asyncio
    async def test_insufficient_data_returns_neutral(self, session: AsyncSession):
        analyzer = CorrelationAnalyzer(session)
        result = await analyzer.analyze()
        assert result.directional_signal == "neutral"
        assert result.dxy_correlation == 0.0
        assert result.reasoning == "Insufficient correlation data"

    @pytest.mark.asyncio
    async def test_bullish_signal_with_falling_dxy_and_yields(
        self, session: AsyncSession, populated_correlation_data
    ):
        analyzer = CorrelationAnalyzer(session)
        result = await analyzer.analyze()
        assert isinstance(result, CorrelationSummary)
        assert result.directional_signal == "bullish"
        assert "DXY falling" in result.reasoning

    @pytest.mark.asyncio
    async def test_bearish_signal_with_rising_dxy(self, session: AsyncSession):
        """Insert data where DXY and yields are rising."""
        now = datetime.now(timezone.utc)
        for i in range(30):
            ts = now - timedelta(hours=30 - i)
            session.add(CorrelationData(asset="DXY", price=100.0 + i * 0.1, timestamp=ts))
            session.add(CorrelationData(asset="US10Y", price=4.0 + i * 0.01, timestamp=ts))
            session.add(CorrelationData(asset="XAU/USD", price=2400.0 - i * 3.0, timestamp=ts))
        await session.commit()

        analyzer = CorrelationAnalyzer(session)
        result = await analyzer.analyze()
        assert result.directional_signal == "bearish"

    @pytest.mark.asyncio
    async def test_correlation_values_are_bounded(
        self, session: AsyncSession, populated_correlation_data
    ):
        analyzer = CorrelationAnalyzer(session)
        result = await analyzer.analyze()
        assert -1.0 <= result.dxy_correlation <= 1.0
        assert -1.0 <= result.us10y_correlation <= 1.0


class TestToSeries:
    def test_sorts_ascending(self):
        from unittest.mock import MagicMock

        now = datetime.now(timezone.utc)
        rows = [
            MagicMock(timestamp=now - timedelta(hours=2), price=100.0),
            MagicMock(timestamp=now, price=102.0),
            MagicMock(timestamp=now - timedelta(hours=1), price=101.0),
        ]
        series = CorrelationAnalyzer._to_series(rows)
        assert list(series.values) == [100.0, 101.0, 102.0]
