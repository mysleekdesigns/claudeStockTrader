"""Market regime detector — classifies current market conditions per timeframe."""

from __future__ import annotations

import enum
from dataclasses import dataclass

import pandas as pd

from backend.database.models import Timeframe
from backend.strategies.indicators import adx, atr, bollinger_bands, ema


class MarketRegime(str, enum.Enum):
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    VOLATILE = "volatile"


@dataclass
class RegimeResult:
    regime: MarketRegime
    confidence: float
    adx_value: float
    atr_ratio: float  # current ATR / 20-period avg ATR


def detect_regime(df: pd.DataFrame) -> RegimeResult:
    """Classify market regime for a single timeframe's candle data.

    Rules:
    - ATR > 2x 20-period average ATR -> Volatile (checked first, overrides trending)
    - ADX > 25 -> Trending (Up or Down based on EMA slope)
    - ADX < 20 + tight Bollinger Bands -> Ranging
    - Otherwise -> Ranging with lower confidence
    """
    if df is None or len(df) < 30:
        return RegimeResult(
            regime=MarketRegime.RANGING, confidence=0.3,
            adx_value=0.0, atr_ratio=1.0,
        )

    close = df["close"]
    adx_series = adx(df, period=14)
    atr_series = atr(df, period=14)
    ema_fast = ema(close, 9)
    ema_slow = ema(close, 21)
    upper, middle, lower = bollinger_bands(close, period=20, std_dev=2.0)

    current_adx = float(adx_series.iloc[-1]) if not pd.isna(adx_series.iloc[-1]) else 0.0
    current_atr = float(atr_series.iloc[-1]) if not pd.isna(atr_series.iloc[-1]) else 0.0
    avg_atr_20 = float(atr_series.iloc[-20:].mean()) if len(atr_series) >= 20 else current_atr

    atr_ratio = current_atr / avg_atr_20 if avg_atr_20 > 0 else 1.0

    # Bollinger Band width relative to middle
    bb_width = float(upper.iloc[-1] - lower.iloc[-1]) if not pd.isna(upper.iloc[-1]) else 0.0
    bb_middle = float(middle.iloc[-1]) if not pd.isna(middle.iloc[-1]) else 1.0
    bb_pct = bb_width / bb_middle if bb_middle > 0 else 0.0

    # Rule 1: Volatile — ATR > 2x average
    if atr_ratio > 2.0:
        confidence = min(0.95, 0.6 + (atr_ratio - 2.0) * 0.15)
        return RegimeResult(
            regime=MarketRegime.VOLATILE, confidence=confidence,
            adx_value=current_adx, atr_ratio=atr_ratio,
        )

    # Rule 2: Trending — ADX > 25
    if current_adx > 25:
        ema_fast_val = float(ema_fast.iloc[-1])
        ema_slow_val = float(ema_slow.iloc[-1])
        is_up = ema_fast_val > ema_slow_val
        confidence = min(0.95, 0.5 + (current_adx - 25) * 0.01)
        return RegimeResult(
            regime=MarketRegime.TRENDING_UP if is_up else MarketRegime.TRENDING_DOWN,
            confidence=confidence,
            adx_value=current_adx, atr_ratio=atr_ratio,
        )

    # Rule 3: Ranging — ADX < 20 + tight BB
    if current_adx < 20 and bb_pct < 0.02:
        confidence = min(0.90, 0.5 + (20 - current_adx) * 0.02)
        return RegimeResult(
            regime=MarketRegime.RANGING, confidence=confidence,
            adx_value=current_adx, atr_ratio=atr_ratio,
        )

    # Default: Ranging with lower confidence
    return RegimeResult(
        regime=MarketRegime.RANGING, confidence=0.4,
        adx_value=current_adx, atr_ratio=atr_ratio,
    )


class MarketRegimeDetector:
    """Detect market regime across all timeframes."""

    def detect_all(
        self, candles: dict[Timeframe, pd.DataFrame]
    ) -> dict[Timeframe, RegimeResult]:
        results: dict[Timeframe, RegimeResult] = {}
        for tf in [Timeframe.M15, Timeframe.H1, Timeframe.H4, Timeframe.D1]:
            df = candles.get(tf)
            if df is not None and not df.empty:
                results[tf] = detect_regime(df)
        return results

    def format_for_prompt(
        self, regimes: dict[Timeframe, RegimeResult]
    ) -> str:
        if not regimes:
            return "No regime data available."
        lines = ["## Market Regime Analysis"]
        for tf in [Timeframe.D1, Timeframe.H4, Timeframe.H1, Timeframe.M15]:
            r = regimes.get(tf)
            if r is None:
                continue
            lines.append(
                f"- {tf.value}: {r.regime.value} (confidence={r.confidence:.2f}, "
                f"ADX={r.adx_value:.1f}, ATR_ratio={r.atr_ratio:.2f})"
            )
        return "\n".join(lines)
