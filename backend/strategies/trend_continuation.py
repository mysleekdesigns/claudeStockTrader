"""Strategy 2 — Trend Continuation.

50/200 EMA on 4h to define trend direction,
pullback to 50 EMA on 1h, engulfing entry.
"""

from __future__ import annotations

import pandas as pd

from backend.database.models import SignalDirection, Timeframe
from backend.strategies.base import SignalCandidate
from backend.strategies.indicators import (
    atr,
    ema,
    is_engulfing_bearish,
    is_engulfing_bullish,
)


class TrendContinuationStrategy:
    name: str = "trend_continuation"

    def __init__(
        self,
        ema_fast: int = 50,
        ema_slow: int = 200,
        pullback_tolerance: float = 0.3,
        sl_atr_mult: float = 1.5,
        tp_atr_mult: float = 3.0,
        atr_period: int = 14,
    ):
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow
        self.pullback_tolerance = pullback_tolerance
        self.sl_atr_mult = sl_atr_mult
        self.tp_atr_mult = tp_atr_mult
        self.atr_period = atr_period

    def evaluate(
        self,
        candles: dict[Timeframe, pd.DataFrame],
    ) -> list[SignalCandidate]:
        h4 = candles.get(Timeframe.H4)
        h1 = candles.get(Timeframe.H1)
        if h4 is None or h1 is None:
            return []
        if len(h4) < self.ema_slow + 5 or len(h1) < self.ema_fast + 5:
            return []

        signals: list[SignalCandidate] = []

        # Compute EMAs on 4h for trend direction
        ema_fast_4h = ema(h4["close"], self.ema_fast)
        ema_slow_4h = ema(h4["close"], self.ema_slow)

        fast_val = float(ema_fast_4h.iloc[-1])
        slow_val = float(ema_slow_4h.iloc[-1])

        if fast_val == slow_val:
            return []

        is_uptrend = fast_val > slow_val

        # Compute 50 EMA on 1h for pullback level
        ema_fast_1h = ema(h1["close"], self.ema_fast)
        atr_1h = atr(h1, self.atr_period)
        current_atr = float(atr_1h.iloc[-1])
        if current_atr <= 0:
            return []

        ema_val_1h = float(ema_fast_1h.iloc[-1])
        latest_1h = h1.iloc[-1]
        price = float(latest_1h["close"])

        # Check if price has pulled back to the 50 EMA zone
        pullback_zone = self.pullback_tolerance * current_atr
        distance_to_ema = abs(price - ema_val_1h)

        if distance_to_ema > pullback_zone:
            return []

        idx = len(h1) - 1

        if is_uptrend and is_engulfing_bullish(h1, idx):
            entry = price
            sl = entry - self.sl_atr_mult * current_atr
            tp = entry + self.tp_atr_mult * current_atr
            rr = abs(tp - entry) / abs(entry - sl) if abs(entry - sl) > 0 else 0
            confidence = self._calc_confidence(
                rr, fast_val, slow_val, distance_to_ema, pullback_zone
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
                            f"4h uptrend (EMA{self.ema_fast}={fast_val:.2f} > EMA{self.ema_slow}={slow_val:.2f}). "
                            f"1h pullback to EMA{self.ema_fast} at {ema_val_1h:.2f}. "
                            f"Bullish engulfing entry at {entry:.2f}. RR={rr:.2f}."
                        ),
                        timeframe_bias=Timeframe.H4,
                        timeframe_entry=Timeframe.H1,
                        atr_value=current_atr,
                    )
                )

        elif not is_uptrend and is_engulfing_bearish(h1, idx):
            entry = price
            sl = entry + self.sl_atr_mult * current_atr
            tp = entry - self.tp_atr_mult * current_atr
            rr = abs(entry - tp) / abs(sl - entry) if abs(sl - entry) > 0 else 0
            confidence = self._calc_confidence(
                rr, fast_val, slow_val, distance_to_ema, pullback_zone
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
                            f"4h downtrend (EMA{self.ema_fast}={fast_val:.2f} < EMA{self.ema_slow}={slow_val:.2f}). "
                            f"1h pullback to EMA{self.ema_fast} at {ema_val_1h:.2f}. "
                            f"Bearish engulfing entry at {entry:.2f}. RR={rr:.2f}."
                        ),
                        timeframe_bias=Timeframe.H4,
                        timeframe_entry=Timeframe.H1,
                        atr_value=current_atr,
                    )
                )

        return signals

    def _calc_confidence(
        self,
        rr: float,
        ema_fast: float,
        ema_slow: float,
        distance_to_ema: float,
        pullback_zone: float,
    ) -> float:
        score = 0.50

        # Reward/risk
        if rr >= 2.0:
            score += 0.15
        elif rr >= 1.5:
            score += 0.10

        # Trend strength — wider EMA separation is stronger
        ema_spread = abs(ema_fast - ema_slow) / ema_slow if ema_slow > 0 else 0
        if ema_spread >= 0.01:
            score += 0.10
        elif ema_spread >= 0.005:
            score += 0.05

        # Pullback precision — closer to EMA = better
        if pullback_zone > 0:
            precision = 1 - (distance_to_ema / pullback_zone)
            score += 0.05 * precision

        return min(score, 1.0)
