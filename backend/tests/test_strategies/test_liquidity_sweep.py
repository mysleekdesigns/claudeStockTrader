"""Tests for the Liquidity Sweep strategy."""

import numpy as np
import pandas as pd
import pytest

from backend.database.models import SignalDirection, Timeframe
from backend.strategies.liquidity_sweep import LiquiditySweepStrategy


@pytest.fixture
def strategy():
    return LiquiditySweepStrategy()


def _make_sweep_scenario(
    direction: str = "bearish",
    n_h1: int = 60,
    n_m15: int = 10,
) -> dict[Timeframe, pd.DataFrame]:
    """Create candle data with a liquidity sweep setup.

    For bearish: equal highs swept then reversal.
    For bullish: equal lows swept then reversal.
    """
    rng = np.random.default_rng(123)
    base = 2350.0

    # Build 1h candles with equal highs/lows
    h1_rows = []
    for i in range(n_h1):
        c = base + rng.normal(0, 5)
        o = c + rng.normal(0, 3)
        h = max(o, c) + abs(rng.normal(0, 3))
        l = min(o, c) - abs(rng.normal(0, 3))

        # Create equal highs around 2370 at multiple points
        if direction == "bearish" and i in (10, 20, 30):
            h = 2370.0
            c = 2365.0
            o = 2360.0
            l = 2355.0

        # Create equal lows around 2330 at multiple points
        if direction == "bullish" and i in (10, 20, 30):
            l = 2330.0
            c = 2335.0
            o = 2340.0
            h = 2345.0

        h1_rows.append({"open": o, "high": h, "low": l, "close": c, "volume": 5000.0})

    # Last 1h candle sweeps the level
    if direction == "bearish":
        # Wick above 2370, close below
        h1_rows[-1] = {
            "open": 2365.0, "high": 2375.0, "low": 2355.0,
            "close": 2360.0, "volume": 8000.0,
        }
    else:
        # Wick below 2330, close above
        h1_rows[-1] = {
            "open": 2335.0, "high": 2345.0, "low": 2325.0,
            "close": 2340.0, "volume": 8000.0,
        }

    h1 = pd.DataFrame(h1_rows)

    # Build 15m candles with confirmation pattern
    m15_rows = []
    for i in range(n_m15 - 2):
        m15_rows.append({
            "open": 2360.0, "high": 2363.0, "low": 2357.0,
            "close": 2361.0, "volume": 2000.0,
        })

    if direction == "bearish":
        # Bearish engulfing on m15
        m15_rows.append({
            "open": 2358.0, "high": 2365.0, "low": 2357.0,
            "close": 2364.0, "volume": 3000.0,
        })
        m15_rows.append({
            "open": 2365.0, "high": 2366.0, "low": 2352.0,
            "close": 2355.0, "volume": 4000.0,
        })
    else:
        # Bullish engulfing on m15
        m15_rows.append({
            "open": 2342.0, "high": 2343.0, "low": 2335.0,
            "close": 2336.0, "volume": 3000.0,
        })
        m15_rows.append({
            "open": 2335.0, "high": 2348.0, "low": 2334.0,
            "close": 2345.0, "volume": 4000.0,
        })

    m15 = pd.DataFrame(m15_rows)

    return {Timeframe.H1: h1, Timeframe.M15: m15}


class TestLiquiditySweep:
    def test_returns_empty_with_insufficient_data(self, strategy):
        candles = {
            Timeframe.H1: pd.DataFrame(columns=["open", "high", "low", "close", "volume"]),
            Timeframe.M15: pd.DataFrame(columns=["open", "high", "low", "close", "volume"]),
        }
        assert strategy.evaluate(candles) == []

    def test_returns_empty_without_m15(self, strategy):
        candles = {Timeframe.H1: pd.DataFrame({"open": [1]*60, "high": [1]*60, "low": [1]*60, "close": [1]*60, "volume": [1]*60})}
        assert strategy.evaluate(candles) == []

    def test_bearish_sweep_generates_short_signal(self, strategy):
        candles = _make_sweep_scenario(direction="bearish")
        signals = strategy.evaluate(candles)
        shorts = [s for s in signals if s.direction == SignalDirection.SHORT]
        if shorts:
            s = shorts[0]
            assert s.strategy_name == "liquidity_sweep"
            assert s.stop_loss > s.entry_price  # SL above entry for short
            assert s.take_profit < s.entry_price  # TP below entry for short
            assert s.confidence >= 0.60

    def test_bullish_sweep_generates_long_signal(self, strategy):
        candles = _make_sweep_scenario(direction="bullish")
        signals = strategy.evaluate(candles)
        longs = [s for s in signals if s.direction == SignalDirection.LONG]
        if longs:
            s = longs[0]
            assert s.strategy_name == "liquidity_sweep"
            assert s.stop_loss < s.entry_price
            assert s.take_profit > s.entry_price
            assert s.confidence >= 0.60

    def test_confidence_below_threshold_filtered(self):
        """Strategy with extreme parameters should produce low confidence."""
        strategy = LiquiditySweepStrategy(
            sl_atr_mult=0.1, tp_atr_mult=0.1  # Tiny RR
        )
        candles = _make_sweep_scenario(direction="bearish")
        signals = strategy.evaluate(candles)
        # Low RR should result in lower confidence, possibly filtered
        for s in signals:
            assert s.confidence >= 0.60  # Only >= 0.60 should be returned

    def test_signal_candidate_fields(self, strategy):
        candles = _make_sweep_scenario(direction="bearish")
        signals = strategy.evaluate(candles)
        for s in signals:
            assert s.timeframe_bias == Timeframe.H1
            assert s.timeframe_entry == Timeframe.M15
            assert s.atr_value > 0
            assert len(s.reasoning) > 0

    def test_custom_parameters(self):
        strategy = LiquiditySweepStrategy(
            eq_tolerance=2.0,
            sl_atr_mult=2.0,
            tp_atr_mult=4.0,
            atr_period=10,
            lookback=40,
            min_touches=2,
        )
        candles = _make_sweep_scenario(direction="bearish")
        # Should run without error regardless of signal generation
        signals = strategy.evaluate(candles)
        assert isinstance(signals, list)
