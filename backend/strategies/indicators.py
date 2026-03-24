"""Pure numpy/pandas technical indicator implementations."""

from __future__ import annotations

import numpy as np
import pandas as pd


def ema(series: pd.Series, period: int) -> pd.Series:
    """Exponential Moving Average."""
    return series.ewm(span=period, adjust=False).mean()


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average True Range.

    Expects DataFrame with 'high', 'low', 'close' columns.
    """
    high = df["high"]
    low = df["low"]
    prev_close = df["close"].shift(1)

    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()

    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return true_range.ewm(span=period, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Relative Strength Index."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)

    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100.0 - (100.0 / (1.0 + rs))


def bollinger_bands(
    series: pd.Series, period: int = 20, std_dev: float = 2.0
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Bollinger Bands.

    Returns:
        (upper_band, middle_band, lower_band)
    """
    middle = series.rolling(window=period).mean()
    std = series.rolling(window=period).std()
    upper = middle + std_dev * std
    lower = middle - std_dev * std
    return upper, middle, lower


def detect_equal_levels(
    series: pd.Series, tolerance: float, lookback: int = 50, min_touches: int = 2
) -> list[float]:
    """Detect equal highs or lows (liquidity pools).

    Groups price levels within `tolerance` of each other and returns levels
    with at least `min_touches` touches.

    Args:
        series: Series of highs or lows.
        tolerance: Maximum distance between prices to be considered equal.
        lookback: Number of recent bars to scan.
        min_touches: Minimum number of touches to qualify as a level.

    Returns:
        List of price levels (averaged from cluster members).
    """
    recent = series.iloc[-lookback:].values
    if len(recent) < min_touches:
        return []

    # Find local extremes (simple peak/trough detection)
    extremes: list[float] = []
    for i in range(1, len(recent) - 1):
        # Local max for highs or local min for lows
        if recent[i] >= recent[i - 1] and recent[i] >= recent[i + 1]:
            extremes.append(float(recent[i]))
        elif recent[i] <= recent[i - 1] and recent[i] <= recent[i + 1]:
            extremes.append(float(recent[i]))

    if not extremes:
        return []

    # Cluster nearby levels
    sorted_extremes = sorted(extremes)
    clusters: list[list[float]] = [[sorted_extremes[0]]]
    for price in sorted_extremes[1:]:
        if abs(price - np.mean(clusters[-1])) <= tolerance:
            clusters[-1].append(price)
        else:
            clusters.append([price])

    return [float(np.mean(c)) for c in clusters if len(c) >= min_touches]


def is_engulfing_bullish(df: pd.DataFrame, idx: int) -> bool:
    """Check if candle at idx is a bullish engulfing pattern."""
    if idx < 1 or idx >= len(df):
        return False
    prev = df.iloc[idx - 1]
    curr = df.iloc[idx]
    return (
        prev["close"] < prev["open"]  # prev bearish
        and curr["close"] > curr["open"]  # curr bullish
        and curr["close"] > prev["open"]
        and curr["open"] <= prev["close"]
    )


def is_engulfing_bearish(df: pd.DataFrame, idx: int) -> bool:
    """Check if candle at idx is a bearish engulfing pattern."""
    if idx < 1 or idx >= len(df):
        return False
    prev = df.iloc[idx - 1]
    curr = df.iloc[idx]
    return (
        prev["close"] > prev["open"]  # prev bullish
        and curr["close"] < curr["open"]  # curr bearish
        and curr["close"] < prev["open"]
        and curr["open"] >= prev["close"]
    )


def is_pin_bar_bullish(df: pd.DataFrame, idx: int, body_ratio: float = 0.3) -> bool:
    """Check if candle at idx is a bullish pin bar (long lower wick)."""
    if idx >= len(df):
        return False
    c = df.iloc[idx]
    total_range = c["high"] - c["low"]
    if total_range == 0:
        return False
    body = abs(c["close"] - c["open"])
    lower_wick = min(c["open"], c["close"]) - c["low"]
    return body / total_range <= body_ratio and lower_wick / total_range >= 0.6


def is_pin_bar_bearish(df: pd.DataFrame, idx: int, body_ratio: float = 0.3) -> bool:
    """Check if candle at idx is a bearish pin bar (long upper wick)."""
    if idx >= len(df):
        return False
    c = df.iloc[idx]
    total_range = c["high"] - c["low"]
    if total_range == 0:
        return False
    body = abs(c["close"] - c["open"])
    upper_wick = c["high"] - max(c["open"], c["close"])
    return body / total_range <= body_ratio and upper_wick / total_range >= 0.6
