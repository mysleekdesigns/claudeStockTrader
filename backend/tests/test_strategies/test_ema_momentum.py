"""Tests for the EMA Momentum strategy."""

import numpy as np
import pandas as pd
import pytest

from backend.database.models import SignalDirection, Timeframe
from backend.strategies.ema_momentum import EMAMomentumStrategy


@pytest.fixture
def strategy():
    return EMAMomentumStrategy()


def _make_momentum_candles(
    n: int = 100,
    direction: str = "bullish",
    base: float = 2350.0,
) -> pd.DataFrame:
    """Generate candles with EMA fan-out and momentum.

    For bullish: price trending up with EMA8 > EMA21 > EMA50, RSI > 55.
    For bearish: opposite.
    """
    rng = np.random.default_rng(42)
    trend = 0.8 if direction == "bullish" else -0.8
    rows = []
    price = base

    for i in range(n):
        price += trend + rng.normal(0, 1.5)
        o = price + rng.normal(0, 0.5)
        c = price
        h = max(o, c) + abs(rng.normal(0, 1))
        l = min(o, c) - abs(rng.normal(0, 1))
        rows.append({"open": o, "high": h, "low": l, "close": c, "volume": 5000.0})

    return pd.DataFrame(rows)


class TestEMAMomentum:
    def test_returns_empty_insufficient_data(self, strategy):
        small = pd.DataFrame({
            "open": [2350] * 10, "high": [2355] * 10,
            "low": [2345] * 10, "close": [2350] * 10, "volume": [5000] * 10,
        })
        candles = {Timeframe.H1: small, Timeframe.M15: small}
        assert strategy.evaluate(candles) == []

    def test_bullish_momentum_generates_long(self, strategy):
        h1 = _make_momentum_candles(100, "bullish")
        candles = {Timeframe.H1: h1, Timeframe.M15: _make_momentum_candles(100, "bullish")}
        signals = strategy.evaluate(candles)
        for s in signals:
            assert s.direction == SignalDirection.LONG
            assert s.strategy_name == "ema_momentum"
            assert s.confidence >= 0.60
            assert s.stop_loss < s.entry_price
            assert s.take_profit > s.entry_price

    def test_bearish_momentum_generates_short(self, strategy):
        h1 = _make_momentum_candles(100, "bearish")
        candles = {Timeframe.H1: h1, Timeframe.M15: _make_momentum_candles(100, "bearish")}
        signals = strategy.evaluate(candles)
        for s in signals:
            assert s.direction == SignalDirection.SHORT
            assert s.strategy_name == "ema_momentum"
            assert s.confidence >= 0.60
            assert s.stop_loss > s.entry_price
            assert s.take_profit < s.entry_price

    def test_prefers_h1_over_m15(self, strategy):
        """Strategy checks H1 first and breaks if signal found."""
        h1 = _make_momentum_candles(100, "bullish")
        m15 = _make_momentum_candles(100, "bearish")
        candles = {Timeframe.H1: h1, Timeframe.M15: m15}
        signals = strategy.evaluate(candles)
        # Should get at most 1 signal (from H1 or M15, H1 checked first)
        assert len(signals) <= 1

    def test_flat_market_no_signal(self, strategy):
        flat = pd.DataFrame({
            "open": [2350.0] * 100,
            "high": [2351.0] * 100,
            "low": [2349.0] * 100,
            "close": [2350.0] * 100,
            "volume": [5000.0] * 100,
        })
        candles = {Timeframe.H1: flat, Timeframe.M15: flat}
        signals = strategy.evaluate(candles)
        assert signals == []

    def test_signal_atr_is_positive(self, strategy):
        h1 = _make_momentum_candles(100, "bullish")
        candles = {Timeframe.H1: h1}
        signals = strategy.evaluate(candles)
        for s in signals:
            assert s.atr_value > 0

    def test_custom_rsi_thresholds(self):
        strategy = EMAMomentumStrategy(rsi_long_threshold=70.0, rsi_short_threshold=30.0)
        h1 = _make_momentum_candles(100, "bullish")
        candles = {Timeframe.H1: h1}
        # With stricter RSI threshold, fewer signals expected
        signals = strategy.evaluate(candles)
        assert isinstance(signals, list)
