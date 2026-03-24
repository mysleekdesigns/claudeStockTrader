"""Tests for technical indicator functions."""

import numpy as np
import pandas as pd
import pytest

from backend.strategies.indicators import (
    adx,
    atr,
    bollinger_bands,
    detect_equal_levels,
    ema,
    is_engulfing_bearish,
    is_engulfing_bullish,
    is_pin_bar_bearish,
    is_pin_bar_bullish,
    rsi,
)


@pytest.fixture
def sample_df() -> pd.DataFrame:
    """Simple OHLCV dataframe for indicator tests."""
    np.random.seed(42)
    n = 100
    closes = 2350 + np.cumsum(np.random.randn(n) * 2)
    highs = closes + np.abs(np.random.randn(n) * 3)
    lows = closes - np.abs(np.random.randn(n) * 3)
    opens = closes + np.random.randn(n) * 1.5
    return pd.DataFrame({
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": np.random.uniform(1000, 10000, n),
    })


class TestEMA:
    def test_ema_length_matches_input(self, sample_df):
        result = ema(sample_df["close"], 20)
        assert len(result) == len(sample_df)

    def test_ema_converges_to_mean(self):
        constant = pd.Series([100.0] * 50)
        result = ema(constant, 10)
        assert abs(result.iloc[-1] - 100.0) < 1e-6

    def test_ema_responds_to_trend(self):
        rising = pd.Series(range(100), dtype=float)
        result = ema(rising, 10)
        # EMA should lag behind actual values in a trend
        assert result.iloc[-1] < 99.0
        assert result.iloc[-1] > 80.0


class TestATR:
    def test_atr_positive(self, sample_df):
        result = atr(sample_df)
        assert (result.dropna() > 0).all()

    def test_atr_length(self, sample_df):
        result = atr(sample_df, period=14)
        assert len(result) == len(sample_df)

    def test_atr_flat_market_is_small(self):
        flat = pd.DataFrame({
            "open": [100.0] * 30,
            "high": [100.5] * 30,
            "low": [99.5] * 30,
            "close": [100.0] * 30,
        })
        result = atr(flat, 14)
        assert result.iloc[-1] < 2.0


class TestRSI:
    def test_rsi_range(self, sample_df):
        result = rsi(sample_df["close"])
        valid = result.dropna()
        assert (valid >= 0).all()
        assert (valid <= 100).all()

    def test_rsi_overbought_on_rising(self):
        rising = pd.Series(range(50), dtype=float)
        result = rsi(rising, 14)
        assert result.iloc[-1] > 70

    def test_rsi_oversold_on_falling(self):
        falling = pd.Series(list(range(50, 0, -1)), dtype=float)
        result = rsi(falling, 14)
        assert result.iloc[-1] < 30


class TestBollingerBands:
    def test_band_ordering(self, sample_df):
        upper, middle, lower = bollinger_bands(sample_df["close"])
        valid_idx = upper.dropna().index
        assert (upper[valid_idx] >= middle[valid_idx]).all()
        assert (middle[valid_idx] >= lower[valid_idx]).all()

    def test_band_width_positive(self, sample_df):
        upper, _, lower = bollinger_bands(sample_df["close"])
        width = (upper - lower).dropna()
        assert (width >= 0).all()


class TestADX:
    def test_adx_range(self, sample_df):
        result = adx(sample_df)
        valid = result.dropna()
        assert (valid >= 0).all()
        assert (valid <= 100).all()

    def test_adx_length(self, sample_df):
        result = adx(sample_df, period=14)
        assert len(result) == len(sample_df)

    def test_adx_strong_trend(self):
        """ADX should be high in a strong unidirectional trend."""
        n = 100
        closes = [2350 + i * 5.0 for i in range(n)]
        highs = [c + 3.0 for c in closes]
        lows = [c - 2.0 for c in closes]
        df = pd.DataFrame({
            "open": closes,
            "high": highs,
            "low": lows,
            "close": closes,
        })
        result = adx(df, period=14)
        # Strong trend should produce ADX > 25
        assert result.iloc[-1] > 25

    def test_adx_flat_market(self):
        """ADX should be low in a flat/ranging market."""
        n = 100
        np.random.seed(123)
        base = 2350.0
        # oscillate around base with small amplitude
        closes = [base + np.sin(i * 0.5) * 2.0 for i in range(n)]
        highs = [c + 1.0 for c in closes]
        lows = [c - 1.0 for c in closes]
        df = pd.DataFrame({
            "open": closes,
            "high": highs,
            "low": lows,
            "close": closes,
        })
        result = adx(df, period=14)
        assert result.iloc[-1] < 25


class TestDetectEqualLevels:
    def test_finds_equal_highs(self):
        # Create series with repeated high around 2400
        data = [2380, 2400, 2390, 2399, 2385, 2401, 2370, 2395, 2400, 2380]
        data.extend([2370 + i for i in range(40)])  # fill to 50
        series = pd.Series(data, dtype=float)
        levels = detect_equal_levels(series, tolerance=3.0, lookback=50, min_touches=2)
        assert len(levels) > 0

    def test_no_levels_in_random_data(self):
        # Each value is far apart
        data = list(range(0, 500, 10))
        series = pd.Series(data, dtype=float)
        levels = detect_equal_levels(series, tolerance=1.0, lookback=50, min_touches=3)
        assert len(levels) == 0

    def test_empty_series(self):
        levels = detect_equal_levels(pd.Series([], dtype=float), tolerance=1.0)
        assert levels == []


class TestEngulfingPatterns:
    def _make_df(self, candles: list[dict]) -> pd.DataFrame:
        return pd.DataFrame(candles)

    def test_bullish_engulfing(self):
        df = self._make_df([
            {"open": 105, "high": 106, "low": 99, "close": 100},   # bearish
            {"open": 99, "high": 108, "low": 98, "close": 107},    # bullish engulfing
        ])
        assert is_engulfing_bullish(df, 1)
        assert not is_engulfing_bearish(df, 1)

    def test_bearish_engulfing(self):
        df = self._make_df([
            {"open": 100, "high": 107, "low": 99, "close": 106},   # bullish
            {"open": 107, "high": 108, "low": 98, "close": 99},    # bearish engulfing
        ])
        assert is_engulfing_bearish(df, 1)
        assert not is_engulfing_bullish(df, 1)

    def test_not_engulfing_when_same_direction(self):
        df = self._make_df([
            {"open": 100, "high": 105, "low": 99, "close": 104},
            {"open": 104, "high": 110, "low": 103, "close": 109},
        ])
        assert not is_engulfing_bullish(df, 1)

    def test_index_out_of_bounds(self):
        df = self._make_df([{"open": 100, "high": 105, "low": 99, "close": 104}])
        assert not is_engulfing_bullish(df, 0)
        assert not is_engulfing_bearish(df, 5)


class TestPinBars:
    def _make_df(self, candles: list[dict]) -> pd.DataFrame:
        return pd.DataFrame(candles)

    def test_bullish_pin_bar(self):
        # Long lower wick, small body at top
        df = self._make_df([{
            "open": 99.5, "high": 100.0, "low": 90.0, "close": 99.8,
        }])
        assert is_pin_bar_bullish(df, 0)

    def test_bearish_pin_bar(self):
        # Long upper wick, small body at bottom
        df = self._make_df([{
            "open": 100.5, "high": 110.0, "low": 100.0, "close": 100.2,
        }])
        assert is_pin_bar_bearish(df, 0)

    def test_not_pin_bar_large_body(self):
        df = self._make_df([{
            "open": 90, "high": 110, "low": 89, "close": 108,
        }])
        assert not is_pin_bar_bullish(df, 0)
        assert not is_pin_bar_bearish(df, 0)

    def test_zero_range_candle(self):
        df = self._make_df([{
            "open": 100, "high": 100, "low": 100, "close": 100,
        }])
        assert not is_pin_bar_bullish(df, 0)
        assert not is_pin_bar_bearish(df, 0)
