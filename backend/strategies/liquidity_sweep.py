"""Strategy 1 — Liquidity Sweep.

Detect equal highs/lows (liquidity pools) on 1h chart,
identify sweep + reversal, 15m confirmation entry.
"""

from __future__ import annotations

import pandas as pd

from backend.database.models import SignalDirection, Timeframe
from backend.strategies.base import SignalCandidate
from backend.strategies.indicators import (
    atr,
    detect_equal_levels,
    is_engulfing_bearish,
    is_engulfing_bullish,
    is_pin_bar_bearish,
    is_pin_bar_bullish,
)


class LiquiditySweepStrategy:
    name: str = "liquidity_sweep"

    def __init__(
        self,
        eq_tolerance: float = 1.5,
        sl_atr_mult: float = 1.5,
        tp_atr_mult: float = 3.0,
        atr_period: int = 14,
        lookback: int = 50,
        min_touches: int = 2,
    ):
        self.eq_tolerance = eq_tolerance
        self.sl_atr_mult = sl_atr_mult
        self.tp_atr_mult = tp_atr_mult
        self.atr_period = atr_period
        self.lookback = lookback
        self.min_touches = min_touches

    def evaluate(
        self,
        candles: dict[Timeframe, pd.DataFrame],
    ) -> list[SignalCandidate]:
        h1 = candles.get(Timeframe.H1)
        m15 = candles.get(Timeframe.M15)
        if h1 is None or m15 is None or len(h1) < self.lookback or len(m15) < 3:
            return []

        signals: list[SignalCandidate] = []
        atr_h1 = atr(h1, self.atr_period)
        current_atr = float(atr_h1.iloc[-1])
        if current_atr <= 0:
            return []

        # Detect equal highs and equal lows on 1h
        equal_highs = detect_equal_levels(
            h1["high"], self.eq_tolerance, self.lookback, self.min_touches
        )
        equal_lows = detect_equal_levels(
            h1["low"], self.eq_tolerance, self.lookback, self.min_touches
        )

        latest_h1 = h1.iloc[-1]
        m15_idx = len(m15) - 1

        # Check for sweep of equal highs (bearish setup)
        for level in equal_highs:
            if latest_h1["high"] > level and latest_h1["close"] < level:
                # Wick swept above, closed back below — bearish reversal
                if is_engulfing_bearish(m15, m15_idx) or is_pin_bar_bearish(m15, m15_idx):
                    entry = float(m15.iloc[-1]["close"])
                    sl = entry + self.sl_atr_mult * current_atr
                    tp = entry - self.tp_atr_mult * current_atr
                    rr = abs(entry - tp) / abs(sl - entry) if abs(sl - entry) > 0 else 0
                    confidence = self._calc_confidence(rr, current_atr, level, latest_h1)
                    if confidence >= 0.60:
                        signals.append(
                            SignalCandidate(
                                strategy_name=self.name,
                                direction=SignalDirection.SHORT,
                                entry_price=entry,
                                stop_loss=sl,
                                take_profit=tp,
                                confidence=confidence,
                                reasoning=(
                                    f"Liquidity sweep above equal highs at {level:.2f}. "
                                    f"Wick to {latest_h1['high']:.2f}, closed back at {latest_h1['close']:.2f}. "
                                    f"15m bearish confirmation. RR={rr:.2f}, ATR={current_atr:.2f}."
                                ),
                                timeframe_bias=Timeframe.H1,
                                timeframe_entry=Timeframe.M15,
                                atr_value=current_atr,
                            )
                        )

        # Check for sweep of equal lows (bullish setup)
        for level in equal_lows:
            if latest_h1["low"] < level and latest_h1["close"] > level:
                # Wick swept below, closed back above — bullish reversal
                if is_engulfing_bullish(m15, m15_idx) or is_pin_bar_bullish(m15, m15_idx):
                    entry = float(m15.iloc[-1]["close"])
                    sl = entry - self.sl_atr_mult * current_atr
                    tp = entry + self.tp_atr_mult * current_atr
                    rr = abs(tp - entry) / abs(entry - sl) if abs(entry - sl) > 0 else 0
                    confidence = self._calc_confidence(rr, current_atr, level, latest_h1)
                    if confidence >= 0.60:
                        signals.append(
                            SignalCandidate(
                                strategy_name=self.name,
                                direction=SignalDirection.LONG,
                                entry_price=entry,
                                stop_loss=sl,
                                take_profit=tp,
                                confidence=confidence,
                                reasoning=(
                                    f"Liquidity sweep below equal lows at {level:.2f}. "
                                    f"Wick to {latest_h1['low']:.2f}, closed back at {latest_h1['close']:.2f}. "
                                    f"15m bullish confirmation. RR={rr:.2f}, ATR={current_atr:.2f}."
                                ),
                                timeframe_bias=Timeframe.H1,
                                timeframe_entry=Timeframe.M15,
                                atr_value=current_atr,
                            )
                        )

        return signals

    def _calc_confidence(
        self, rr: float, current_atr: float, level: float, candle: pd.Series
    ) -> float:
        """Calculate confidence score based on signal quality factors."""
        score = 0.50

        # Reward/risk quality
        if rr >= 2.0:
            score += 0.15
        elif rr >= 1.5:
            score += 0.10

        # Sweep depth — bigger wick beyond level = stronger signal
        sweep_depth = max(abs(candle["high"] - level), abs(candle["low"] - level))
        if current_atr > 0 and sweep_depth / current_atr >= 0.3:
            score += 0.10

        # Clean close back inside
        if current_atr > 0:
            close_distance = min(abs(candle["close"] - level), current_atr)
            score += 0.05 * (1 - close_distance / current_atr)

        return min(score, 1.0)
