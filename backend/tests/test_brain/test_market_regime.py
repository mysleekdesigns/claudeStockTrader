"""Tests for market regime detection."""

import numpy as np
import pandas as pd
import pytest

from backend.brain.market_regime import (
    MarketRegime,
    MarketRegimeDetector,
    RegimeResult,
    detect_regime,
)
from backend.database.models import Timeframe


def _make_trending_df(n: int = 100, direction: float = 5.0) -> pd.DataFrame:
    """Create strongly trending candle data."""
    closes = [2350 + i * direction for i in range(n)]
    highs = [c + 3.0 for c in closes]
    lows = [c - 2.0 for c in closes]
    return pd.DataFrame({
        "open": closes,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": [5000.0] * n,
    })


def _make_ranging_df(n: int = 100) -> pd.DataFrame:
    """Create ranging/sideways candle data with small oscillations."""
    base = 2350.0
    closes = [base + np.sin(i * 0.3) * 1.5 for i in range(n)]
    highs = [c + 0.8 for c in closes]
    lows = [c - 0.8 for c in closes]
    return pd.DataFrame({
        "open": closes,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": [5000.0] * n,
    })


def _make_volatile_df(n: int = 100) -> pd.DataFrame:
    """Create volatile candle data with large ATR spikes at the end."""
    rng = np.random.default_rng(42)
    closes = [2350.0]
    for i in range(n - 1):
        # Normal volatility for first 70 bars, then spike
        vol = 3.0 if i < 70 else 50.0
        closes.append(closes[-1] + rng.normal(0, vol))
    highs = [c + abs(rng.normal(0, 30 if i >= 70 else 2)) for i, c in enumerate(closes)]
    lows = [c - abs(rng.normal(0, 30 if i >= 70 else 2)) for i, c in enumerate(closes)]
    return pd.DataFrame({
        "open": closes,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": [5000.0] * n,
    })


class TestDetectRegime:
    def test_trending_up(self):
        df = _make_trending_df(100, direction=5.0)
        result = detect_regime(df)
        assert result.regime == MarketRegime.TRENDING_UP
        assert result.adx_value > 25
        assert result.confidence > 0.4

    def test_trending_down(self):
        df = _make_trending_df(100, direction=-5.0)
        result = detect_regime(df)
        assert result.regime == MarketRegime.TRENDING_DOWN
        assert result.adx_value > 25

    def test_ranging_market(self):
        df = _make_ranging_df(100)
        result = detect_regime(df)
        assert result.regime == MarketRegime.RANGING

    def test_short_data_returns_ranging(self):
        df = pd.DataFrame({
            "open": [2350.0] * 10,
            "high": [2355.0] * 10,
            "low": [2345.0] * 10,
            "close": [2350.0] * 10,
        })
        result = detect_regime(df)
        assert result.regime == MarketRegime.RANGING
        assert result.confidence == 0.3

    def test_none_df(self):
        result = detect_regime(None)
        assert result.regime == MarketRegime.RANGING
        assert result.confidence == 0.3

    def test_result_has_valid_fields(self):
        df = _make_trending_df(100)
        result = detect_regime(df)
        assert isinstance(result, RegimeResult)
        assert 0.0 <= result.confidence <= 1.0
        assert result.atr_ratio > 0


class TestMarketRegimeDetector:
    def test_detect_all_returns_per_timeframe(self):
        detector = MarketRegimeDetector()
        candles = {
            Timeframe.M15: _make_ranging_df(200),
            Timeframe.H1: _make_trending_df(200),
            Timeframe.H4: _make_trending_df(200),
            Timeframe.D1: _make_ranging_df(100),
        }
        results = detector.detect_all(candles)
        assert Timeframe.M15 in results
        assert Timeframe.H1 in results
        assert Timeframe.H4 in results
        assert Timeframe.D1 in results

    def test_detect_all_skips_missing_timeframes(self):
        detector = MarketRegimeDetector()
        candles = {Timeframe.H1: _make_trending_df(200)}
        results = detector.detect_all(candles)
        assert Timeframe.H1 in results
        assert Timeframe.M15 not in results

    def test_format_for_prompt(self):
        detector = MarketRegimeDetector()
        candles = {
            Timeframe.H1: _make_trending_df(200),
            Timeframe.D1: _make_ranging_df(100),
        }
        results = detector.detect_all(candles)
        text = detector.format_for_prompt(results)
        assert "Market Regime Analysis" in text
        assert "1h" in text
        assert "1d" in text

    def test_format_empty(self):
        detector = MarketRegimeDetector()
        text = detector.format_for_prompt({})
        assert "No regime data" in text
