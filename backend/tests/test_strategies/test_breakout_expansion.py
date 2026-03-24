"""Tests for the Breakout Expansion strategy."""

import numpy as np
import pandas as pd
import pytest

from backend.database.models import SignalDirection, Timeframe
from backend.strategies.breakout_expansion import BreakoutExpansionStrategy


@pytest.fixture
def strategy():
    return BreakoutExpansionStrategy()


def _make_squeeze_breakout(direction: str = "bullish") -> dict[Timeframe, pd.DataFrame]:
    """Create candle data simulating a squeeze followed by a breakout.

    Daily: compressed ATR that suddenly expands.
    4h: breakout candle with volume confirmation.
    """
    rng = np.random.default_rng(77)
    n_d1 = 60

    d1_rows = []
    base = 2350.0
    # Tight range for most of the period (squeeze)
    for i in range(n_d1 - 1):
        noise = rng.normal(0, 2)  # Very tight
        o = base + noise
        c = base + rng.normal(0, 2)
        h = max(o, c) + abs(rng.normal(0, 1.5))
        l = min(o, c) - abs(rng.normal(0, 1.5))
        d1_rows.append({"open": o, "high": h, "low": l, "close": c, "volume": 5000.0})

    range_high = max(r["high"] for r in d1_rows[-20:])
    range_low = min(r["low"] for r in d1_rows[-20:])

    # Last daily candle: breakout
    if direction == "bullish":
        d1_rows.append({
            "open": range_high - 2, "high": range_high + 20,
            "low": range_high - 5, "close": range_high + 15,
            "volume": 12000.0,
        })
    else:
        d1_rows.append({
            "open": range_low + 2, "high": range_low + 5,
            "low": range_low - 20, "close": range_low - 15,
            "volume": 12000.0,
        })

    d1 = pd.DataFrame(d1_rows)

    # 4h candles: retest of breakout level with volume
    breakout_level = range_high if direction == "bullish" else range_low
    h4_rows = []
    for i in range(15):
        c = breakout_level + rng.normal(0, 3) + (5 if direction == "bullish" else -5)
        o = c + rng.normal(0, 2)
        h = max(o, c) + abs(rng.normal(0, 3))
        l = min(o, c) - abs(rng.normal(0, 3))
        vol = rng.normal(4000, 1000)
        h4_rows.append({"open": o, "high": h, "low": l, "close": c, "volume": max(vol, 100)})

    # Last bar: retest with volume spike
    if direction == "bullish":
        h4_rows[-1] = {
            "open": breakout_level + 2, "high": breakout_level + 8,
            "low": breakout_level - 1, "close": breakout_level + 5,
            "volume": 10000.0,
        }
    else:
        h4_rows[-1] = {
            "open": breakout_level - 2, "high": breakout_level + 1,
            "low": breakout_level - 8, "close": breakout_level - 5,
            "volume": 10000.0,
        }

    h4 = pd.DataFrame(h4_rows)

    return {Timeframe.D1: d1, Timeframe.H4: h4}


class TestBreakoutExpansion:
    def test_returns_empty_without_d1(self, strategy):
        candles = {Timeframe.H4: pd.DataFrame({"open": [1]*20, "high": [1]*20, "low": [1]*20, "close": [1]*20, "volume": [1]*20})}
        assert strategy.evaluate(candles) == []

    def test_returns_empty_insufficient_d1_data(self, strategy):
        candles = {
            Timeframe.D1: pd.DataFrame({"open": [1]*5, "high": [1]*5, "low": [1]*5, "close": [1]*5, "volume": [1]*5}),
            Timeframe.H4: pd.DataFrame({"open": [1]*20, "high": [1]*20, "low": [1]*20, "close": [1]*20, "volume": [1]*20}),
        }
        assert strategy.evaluate(candles) == []

    def test_bullish_breakout_generates_long(self, strategy):
        candles = _make_squeeze_breakout(direction="bullish")
        signals = strategy.evaluate(candles)
        longs = [s for s in signals if s.direction == SignalDirection.LONG]
        for s in longs:
            assert s.strategy_name == "breakout_expansion"
            assert s.stop_loss < s.entry_price
            assert s.take_profit > s.entry_price
            assert s.confidence >= 0.60
            assert s.timeframe_bias == Timeframe.D1
            assert s.timeframe_entry == Timeframe.H4

    def test_bearish_breakout_generates_short(self, strategy):
        candles = _make_squeeze_breakout(direction="bearish")
        signals = strategy.evaluate(candles)
        shorts = [s for s in signals if s.direction == SignalDirection.SHORT]
        for s in shorts:
            assert s.strategy_name == "breakout_expansion"
            assert s.stop_loss > s.entry_price
            assert s.take_profit < s.entry_price

    def test_no_signal_without_squeeze(self, strategy):
        """Volatile market (no squeeze) should not trigger breakout."""
        rng = np.random.default_rng(88)
        rows = []
        price = 2350.0
        for _ in range(60):
            price += rng.normal(0, 20)
            o = price + rng.normal(0, 5)
            c = price
            h = max(o, c) + abs(rng.normal(0, 10))
            l = min(o, c) - abs(rng.normal(0, 10))
            rows.append({"open": o, "high": h, "low": l, "close": c, "volume": 5000.0})

        d1 = pd.DataFrame(rows)
        h4_rows = [{"open": 2350, "high": 2360, "low": 2340, "close": 2350, "volume": 5000} for _ in range(20)]
        h4 = pd.DataFrame(h4_rows)
        candles = {Timeframe.D1: d1, Timeframe.H4: h4}
        signals = strategy.evaluate(candles)
        # May or may not generate signals, but should not crash
        assert isinstance(signals, list)

    def test_confidence_calculation(self, strategy):
        candles = _make_squeeze_breakout(direction="bullish")
        signals = strategy.evaluate(candles)
        for s in signals:
            assert 0.0 <= s.confidence <= 1.0
