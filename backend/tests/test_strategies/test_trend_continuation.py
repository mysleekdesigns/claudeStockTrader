"""Tests for the Trend Continuation strategy."""

import numpy as np
import pandas as pd
import pytest

from backend.database.models import SignalDirection, Timeframe
from backend.strategies.trend_continuation import TrendContinuationStrategy


@pytest.fixture
def strategy():
    return TrendContinuationStrategy()


def _make_uptrend_candles(n: int, base: float, trend: float) -> pd.DataFrame:
    """Generate uptrending candle data."""
    rng = np.random.default_rng(55)
    rows = []
    price = base
    for _ in range(n):
        price += trend + rng.normal(0, 2)
        o = price + rng.normal(0, 1)
        c = price
        h = max(o, c) + abs(rng.normal(0, 2))
        l = min(o, c) - abs(rng.normal(0, 2))
        rows.append({"open": o, "high": h, "low": l, "close": c, "volume": 5000.0})
    return pd.DataFrame(rows)


def _make_downtrend_candles(n: int, base: float, trend: float) -> pd.DataFrame:
    """Generate downtrending candle data."""
    rng = np.random.default_rng(55)
    rows = []
    price = base
    for _ in range(n):
        price -= trend + rng.normal(0, 2)
        o = price + rng.normal(0, 1)
        c = price
        h = max(o, c) + abs(rng.normal(0, 2))
        l = min(o, c) - abs(rng.normal(0, 2))
        rows.append({"open": o, "high": h, "low": l, "close": c, "volume": 5000.0})
    return pd.DataFrame(rows)


class TestTrendContinuation:
    def test_returns_empty_without_h4(self, strategy):
        candles = {Timeframe.H1: _make_uptrend_candles(100, 2350, 1.0)}
        assert strategy.evaluate(candles) == []

    def test_returns_empty_without_h1(self, strategy):
        candles = {Timeframe.H4: _make_uptrend_candles(250, 2350, 2.0)}
        assert strategy.evaluate(candles) == []

    def test_returns_empty_insufficient_data(self, strategy):
        candles = {
            Timeframe.H4: _make_uptrend_candles(10, 2350, 2.0),
            Timeframe.H1: _make_uptrend_candles(10, 2350, 1.0),
        }
        assert strategy.evaluate(candles) == []

    def test_uptrend_signal_is_long(self, strategy):
        """In a strong uptrend with pullback to EMA, signals should be LONG."""
        # Strong uptrend on 4h
        h4 = _make_uptrend_candles(250, 2200, 2.0)
        # 1h with pullback to 50 EMA zone + bullish engulfing at end
        h1 = _make_uptrend_candles(100, 2300, 0.5)

        # Force last two candles to be bullish engulfing near EMA
        ema_approx = h1["close"].ewm(span=50, adjust=False).mean().iloc[-1]
        h1.iloc[-2, h1.columns.get_loc("open")] = ema_approx + 2
        h1.iloc[-2, h1.columns.get_loc("close")] = ema_approx - 1
        h1.iloc[-2, h1.columns.get_loc("high")] = ema_approx + 3
        h1.iloc[-2, h1.columns.get_loc("low")] = ema_approx - 2

        h1.iloc[-1, h1.columns.get_loc("open")] = ema_approx - 2
        h1.iloc[-1, h1.columns.get_loc("close")] = ema_approx + 4
        h1.iloc[-1, h1.columns.get_loc("high")] = ema_approx + 5
        h1.iloc[-1, h1.columns.get_loc("low")] = ema_approx - 3

        candles = {Timeframe.H4: h4, Timeframe.H1: h1}
        signals = strategy.evaluate(candles)
        for s in signals:
            assert s.direction == SignalDirection.LONG
            assert s.strategy_name == "trend_continuation"
            assert s.timeframe_bias == Timeframe.H4
            assert s.confidence >= 0.60

    def test_flat_market_no_signal(self, strategy):
        """When 50 EMA == 200 EMA, no signal should be generated."""
        flat = pd.DataFrame({
            "open": [2350.0] * 250,
            "high": [2351.0] * 250,
            "low": [2349.0] * 250,
            "close": [2350.0] * 250,
            "volume": [5000.0] * 250,
        })
        candles = {Timeframe.H4: flat, Timeframe.H1: flat.iloc[:100].copy()}
        signals = strategy.evaluate(candles)
        assert signals == []

    def test_signal_has_correct_sl_tp_for_long(self, strategy):
        h4 = _make_uptrend_candles(250, 2200, 2.0)
        h1 = _make_uptrend_candles(100, 2300, 0.5)
        candles = {Timeframe.H4: h4, Timeframe.H1: h1}
        signals = strategy.evaluate(candles)
        for s in signals:
            if s.direction == SignalDirection.LONG:
                assert s.stop_loss < s.entry_price
                assert s.take_profit > s.entry_price
            else:
                assert s.stop_loss > s.entry_price
                assert s.take_profit < s.entry_price
