"""Strategy 3 — Breakout Expansion.

Identify consolidation range on daily (compressed ATR),
breakout confirmed on 4h/1h with expanding volume,
entry on retest of broken level.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from backend.database.models import SignalDirection, Timeframe
from backend.strategies.base import SignalCandidate
from backend.strategies.indicators import atr


class BreakoutExpansionStrategy:
    name: str = "breakout_expansion"

    def __init__(
        self,
        squeeze_period: int = 20,
        breakout_atr_mult: float = 1.5,
        volume_threshold: float = 1.3,
        sl_atr_mult: float = 1.5,
        tp_atr_mult: float = 3.0,
        atr_period: int = 14,
        retest_tolerance: float = 0.5,
    ):
        self.squeeze_period = squeeze_period
        self.breakout_atr_mult = breakout_atr_mult
        self.volume_threshold = volume_threshold
        self.sl_atr_mult = sl_atr_mult
        self.tp_atr_mult = tp_atr_mult
        self.atr_period = atr_period
        self.retest_tolerance = retest_tolerance

    def evaluate(
        self,
        candles: dict[Timeframe, pd.DataFrame],
    ) -> list[SignalCandidate]:
        d1 = candles.get(Timeframe.D1)
        h4 = candles.get(Timeframe.H4)
        h1 = candles.get(Timeframe.H1)
        if d1 is None or len(d1) < self.squeeze_period + self.atr_period + 5:
            return []
        if h4 is None or len(h4) < 10:
            return []

        signals: list[SignalCandidate] = []

        # Detect consolidation on daily via compressed ATR
        atr_d1 = atr(d1, self.atr_period)
        atr_sma = atr_d1.rolling(window=self.squeeze_period).mean()

        current_atr_d1 = float(atr_d1.iloc[-1])
        avg_atr_d1 = float(atr_sma.iloc[-1])

        if avg_atr_d1 <= 0:
            return []

        # Is the market in a squeeze? (current ATR compressed relative to average)
        # We look for a recent squeeze that has now expanded
        prev_atr_d1 = float(atr_d1.iloc[-2])
        was_squeezed = prev_atr_d1 < avg_atr_d1 * 0.8
        is_expanding = current_atr_d1 > prev_atr_d1

        if not (was_squeezed and is_expanding):
            return []

        # Define consolidation range from the squeeze period
        squeeze_window = d1.iloc[-(self.squeeze_period + 1) : -1]
        range_high = float(squeeze_window["high"].max())
        range_low = float(squeeze_window["low"].min())

        latest_d1 = d1.iloc[-1]

        # Use 4h for confirmation and entry timeframe
        atr_h4 = atr(h4, self.atr_period)
        current_atr_h4 = float(atr_h4.iloc[-1])
        if current_atr_h4 <= 0:
            return []

        # Volume check on 4h
        avg_volume = float(h4["volume"].iloc[-10:].mean()) if len(h4) >= 10 else 0
        current_volume = float(h4.iloc[-1]["volume"])
        volume_confirmed = avg_volume > 0 and current_volume >= avg_volume * self.volume_threshold

        latest_h4 = h4.iloc[-1]
        price = float(latest_h4["close"])
        retest_zone = self.retest_tolerance * current_atr_h4

        # Bullish breakout — price closed above range, now retesting
        if float(latest_d1["close"]) > range_high:
            if abs(price - range_high) <= retest_zone and price > range_high:
                entry = price
                sl = entry - self.sl_atr_mult * current_atr_h4
                tp = entry + self.tp_atr_mult * current_atr_h4
                rr = abs(tp - entry) / abs(entry - sl) if abs(entry - sl) > 0 else 0
                confidence = self._calc_confidence(
                    rr, volume_confirmed, current_atr_d1, avg_atr_d1
                )
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
                                f"Breakout above consolidation range [{range_low:.2f}-{range_high:.2f}]. "
                                f"ATR expanding ({current_atr_d1:.2f} vs avg {avg_atr_d1:.2f}). "
                                f"Retest entry at {entry:.2f}. "
                                f"Volume {'confirmed' if volume_confirmed else 'not confirmed'}. RR={rr:.2f}."
                            ),
                            timeframe_bias=Timeframe.D1,
                            timeframe_entry=Timeframe.H4,
                            atr_value=current_atr_h4,
                        )
                    )

        # Bearish breakout — price closed below range, now retesting
        if float(latest_d1["close"]) < range_low:
            if abs(price - range_low) <= retest_zone and price < range_low:
                entry = price
                sl = entry + self.sl_atr_mult * current_atr_h4
                tp = entry - self.tp_atr_mult * current_atr_h4
                rr = abs(entry - tp) / abs(sl - entry) if abs(sl - entry) > 0 else 0
                confidence = self._calc_confidence(
                    rr, volume_confirmed, current_atr_d1, avg_atr_d1
                )
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
                                f"Breakout below consolidation range [{range_low:.2f}-{range_high:.2f}]. "
                                f"ATR expanding ({current_atr_d1:.2f} vs avg {avg_atr_d1:.2f}). "
                                f"Retest entry at {entry:.2f}. "
                                f"Volume {'confirmed' if volume_confirmed else 'not confirmed'}. RR={rr:.2f}."
                            ),
                            timeframe_bias=Timeframe.D1,
                            timeframe_entry=Timeframe.H4,
                            atr_value=current_atr_h4,
                        )
                    )

        return signals

    def _calc_confidence(
        self,
        rr: float,
        volume_confirmed: bool,
        current_atr: float,
        avg_atr: float,
    ) -> float:
        score = 0.50

        # Reward/risk
        if rr >= 2.0:
            score += 0.15
        elif rr >= 1.5:
            score += 0.10

        # Volume confirmation
        if volume_confirmed:
            score += 0.10

        # ATR expansion strength
        if avg_atr > 0:
            expansion = current_atr / avg_atr
            if expansion >= 1.5:
                score += 0.10
            elif expansion >= 1.2:
                score += 0.05

        return min(score, 1.0)
