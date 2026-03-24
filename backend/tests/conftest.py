"""Shared test fixtures for the claudeStockTrader backend."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pandas as pd
import pytest
import pytest_asyncio
from sqlalchemy import StaticPool, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Register JSONB as JSON for SQLite type compiler (used in tests)
from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler

if not hasattr(SQLiteTypeCompiler, "visit_JSONB"):
    def _visit_jsonb(self, type_, **kw):
        return "JSON"
    SQLiteTypeCompiler.visit_JSONB = _visit_jsonb

from backend.database.models import (
    Base,
    Candle,
    RiskState,
    Signal,
    SignalDirection,
    SignalStatus,
    Timeframe,
)


# ---------------------------------------------------------------------------
# Async SQLite engine for tests (in-memory, no external DB required)
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def async_engine():
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # SQLite needs PRAGMA for FK enforcement
    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def session(async_engine):
    factory = async_sessionmaker(
        async_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with factory() as session:
        yield session


# ---------------------------------------------------------------------------
# Candle data generators
# ---------------------------------------------------------------------------

GOLD_BASE_PRICE = 2350.0


def _generate_candles(
    n: int,
    base_price: float = GOLD_BASE_PRICE,
    interval_minutes: int = 60,
    volatility: float = 15.0,
    trend: float = 0.0,
    start_time: datetime | None = None,
) -> pd.DataFrame:
    """Generate realistic XAU/USD OHLCV candle data.

    Args:
        n: Number of candles.
        base_price: Starting price.
        interval_minutes: Candle interval in minutes.
        volatility: Price volatility (ATR-like range per candle).
        trend: Upward/downward bias per candle.
        start_time: Start timestamp (defaults to UTC now minus n intervals).
    """
    rng = np.random.default_rng(42)
    if start_time is None:
        start_time = datetime.now(timezone.utc) - timedelta(minutes=interval_minutes * n)

    timestamps = [start_time + timedelta(minutes=interval_minutes * i) for i in range(n)]
    closes = [base_price]
    for _ in range(n - 1):
        change = rng.normal(trend, volatility)
        closes.append(closes[-1] + change)

    rows = []
    for i, ts in enumerate(timestamps):
        c = closes[i]
        noise = volatility * 0.5
        o = c + rng.normal(0, noise * 0.3)
        h = max(o, c) + abs(rng.normal(0, noise * 0.5))
        l = min(o, c) - abs(rng.normal(0, noise * 0.5))
        vol = max(100, rng.normal(5000, 2000))
        rows.append({
            "timestamp": ts,
            "open": round(o, 2),
            "high": round(h, 2),
            "low": round(l, 2),
            "close": round(c, 2),
            "volume": round(vol, 2),
        })

    return pd.DataFrame(rows)


@pytest.fixture
def candles_m15() -> pd.DataFrame:
    """200 bars of 15-minute XAU/USD candles."""
    return _generate_candles(200, interval_minutes=15, volatility=5.0)


@pytest.fixture
def candles_h1() -> pd.DataFrame:
    """200 bars of 1-hour XAU/USD candles."""
    return _generate_candles(200, interval_minutes=60, volatility=12.0)


@pytest.fixture
def candles_h4() -> pd.DataFrame:
    """250 bars of 4-hour XAU/USD candles."""
    return _generate_candles(250, interval_minutes=240, volatility=20.0)


@pytest.fixture
def candles_d1() -> pd.DataFrame:
    """100 bars of daily XAU/USD candles."""
    return _generate_candles(100, interval_minutes=1440, volatility=30.0)


@pytest.fixture
def all_candles(
    candles_m15: pd.DataFrame,
    candles_h1: pd.DataFrame,
    candles_h4: pd.DataFrame,
    candles_d1: pd.DataFrame,
) -> dict[Timeframe, pd.DataFrame]:
    """All timeframes as a dict, as strategies expect."""
    return {
        Timeframe.M15: candles_m15,
        Timeframe.H1: candles_h1,
        Timeframe.H4: candles_h4,
        Timeframe.D1: candles_d1,
    }


# ---------------------------------------------------------------------------
# Candle data that triggers specific patterns
# ---------------------------------------------------------------------------

def _make_engulfing_bullish_candles(n: int = 10, price: float = 2350.0) -> pd.DataFrame:
    """Create candle data where the last candle is a bullish engulfing."""
    rng = np.random.default_rng(99)
    base_time = datetime.now(timezone.utc) - timedelta(hours=n)
    rows = []
    for i in range(n - 2):
        o = price + rng.normal(0, 3)
        c = o + rng.normal(0, 3)
        h = max(o, c) + abs(rng.normal(0, 2))
        l = min(o, c) - abs(rng.normal(0, 2))
        rows.append({
            "timestamp": base_time + timedelta(hours=i),
            "open": round(o, 2), "high": round(h, 2),
            "low": round(l, 2), "close": round(c, 2), "volume": 5000.0,
        })

    # Second-to-last: bearish candle
    rows.append({
        "timestamp": base_time + timedelta(hours=n - 2),
        "open": price + 5, "high": price + 7, "low": price - 2,
        "close": price - 1, "volume": 5000.0,
    })
    # Last: bullish engulfing (curr close > prev open, curr open <= prev close)
    rows.append({
        "timestamp": base_time + timedelta(hours=n - 1),
        "open": price - 2, "high": price + 10, "low": price - 3,
        "close": price + 8, "volume": 7000.0,
    })
    return pd.DataFrame(rows)


@pytest.fixture
def engulfing_bullish_m15() -> pd.DataFrame:
    return _make_engulfing_bullish_candles(50, 2350.0)


# ---------------------------------------------------------------------------
# Mock external services
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_redis():
    """Fake async Redis client for tests."""
    redis = AsyncMock()
    redis.ping = AsyncMock(return_value=True)
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock()
    redis.publish = AsyncMock()
    redis.zremrangebyscore = AsyncMock()
    redis.zcard = AsyncMock(return_value=0)
    redis.zadd = AsyncMock()
    redis.expire = AsyncMock()
    redis.zrem = AsyncMock()
    redis.pipeline = MagicMock()
    pipe = AsyncMock()
    pipe.execute = AsyncMock(return_value=[0, 0, 0, True])
    redis.pipeline.return_value = pipe
    # Allow use as context manager for aclose
    redis.aclose = AsyncMock()
    return redis


@pytest.fixture
def mock_claude_client():
    """Fake Claude client returning predictable decisions."""
    client = AsyncMock()
    client.decide = AsyncMock(return_value='{"activated_strategies": ["liquidity_sweep", "trend_continuation", "breakout_expansion", "ema_momentum"], "suppressed_strategies": [], "position_size_multiplier": 1.0, "reasoning": "Test decision"}')
    client.analyze = AsyncMock(return_value="Test MC summary")
    return client


# ---------------------------------------------------------------------------
# Risk state fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def clean_risk_state(session: AsyncSession) -> RiskState:
    """Create a fresh risk state for today with no losses."""
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    state = RiskState(
        date=today, daily_loss_pct=0.0, consecutive_stops=0, is_shutdown=False
    )
    session.add(state)
    await session.commit()
    await session.refresh(state)
    return state


@pytest_asyncio.fixture
async def risk_state_near_limit(session: AsyncSession) -> RiskState:
    """Risk state with 7 consecutive stops (1 away from circuit breaker)."""
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    state = RiskState(
        date=today, daily_loss_pct=0.015, consecutive_stops=7, is_shutdown=False
    )
    session.add(state)
    await session.commit()
    await session.refresh(state)
    return state


# ---------------------------------------------------------------------------
# Signal fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def sample_signals(session: AsyncSession) -> list[Signal]:
    """Create a mix of pending, won, and lost signals."""
    now = datetime.now(timezone.utc)
    signals = [
        Signal(
            strategy_name="liquidity_sweep",
            direction=SignalDirection.LONG,
            entry_price=2340.0,
            stop_loss=2320.0,
            take_profit=2380.0,
            confidence_score=0.75,
            reasoning="Test signal 1",
            status=SignalStatus.PENDING,
        ),
        Signal(
            strategy_name="trend_continuation",
            direction=SignalDirection.SHORT,
            entry_price=2360.0,
            stop_loss=2380.0,
            take_profit=2320.0,
            confidence_score=0.68,
            reasoning="Test signal 2",
            status=SignalStatus.WON,
            pips_result=40.0,
            resolved_at=now - timedelta(hours=2),
        ),
        Signal(
            strategy_name="ema_momentum",
            direction=SignalDirection.LONG,
            entry_price=2350.0,
            stop_loss=2330.0,
            take_profit=2390.0,
            confidence_score=0.82,
            reasoning="Test signal 3",
            status=SignalStatus.LOST,
            pips_result=-20.0,
            resolved_at=now - timedelta(hours=1),
        ),
    ]
    for s in signals:
        session.add(s)
    await session.commit()
    for s in signals:
        await session.refresh(s)
    return signals
