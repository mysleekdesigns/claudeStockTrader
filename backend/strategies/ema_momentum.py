"""Strategy 4 — EMA Momentum.

8/21/50 EMA fan-out on 15m and 1h,
price rides 8 EMA,
momentum confirmed by RSI > 55 (long) or < 45 (short).
"""

from __future__ import annotations

import pandas as pd

from backend.database.models import SignalDirection, Timeframe
from backend.strategies.base import SignalCandidate
from backend.strategies.indicators import atr, ema, rsi


class EMAMomentumStrategy:
    name: str = "ema_momentum"

    def __init__(
        self,
        ema_fast: int = 8,
        ema_mid: int = 21,
        ema_slow: int = 50,
        rsi_period: int = 14,
        rsi_long_threshold: float = 55.0,
        rsi_short_threshold: float = 45.0,
        sl_atr_mult: float = 1.5,
        tp_atr_mult: float = 3.0,
        atr_period: int = 14,
        ride_tolerance: float = 0.3,
    ):
        self.ema_fast = ema_fast
        self.ema_mid = ema_mid
        self.ema_slow = ema_slow
        self.rsi_period = rsi_period
        self.rsi_long_threshold = rsi_long_threshold
        self.rsi_short_threshold = rsi_short_threshold
        self.sl_atr_mult = sl_atr_mult
        self.tp_atr_mult = tp_atr_mult
        self.atr_period = atr_period
        self.ride_tolerance = ride_tolerance

    def evaluate(
        self,
        candles: dict[Timeframe, pd.DataFrame],
    ) -> list[SignalCandidate]:
        signals: list[SignalCandidate] = []

        # Check both 15m and 1h — prefer 1h if both signal
        for tf, tf_enum in [(Timeframe.H1, Timeframe.H1), (Timeframe.M15, Timeframe.M15)]:
            df = candles.get(tf)
            if df is None or len(df) < self.ema_slow + self.rsi_period + 5:
                continue

            signal = self._evaluate_timeframe(df, tf_enum)
            if signal is not None:
                signals.append(signal)
                break  # Take the higher-timeframe signal first

        return signals

    def _evaluate_timeframe(
        self, df: pd.DataFrame, timeframe: Timeframe
    ) -> SignalCandidate | None:
        ema_fast_s = ema(df["close"], self.ema_fast)
        ema_mid_s = ema(df["close"], self.ema_mid)
        ema_slow_s = ema(df["close"], self.ema_slow)
        rsi_s = rsi(df["close"], self.rsi_period)
        atr_s = atr(df, self.atr_period)

        fast_val = float(ema_fast_s.iloc[-1])
        mid_val = float(ema_mid_s.iloc[-1])
        slow_val = float(ema_slow_s.iloc[-1])
        rsi_val = float(rsi_s.iloc[-1])
        current_atr = float(atr_s.iloc[-1])

        if current_atr <= 0:
            return None

        price = float(df.iloc[-1]["close"])

        # Check for bullish fan-out: fast > mid > slow, price near fast EMA
        bullish_fan = fast_val > mid_val > slow_val
        bearish_fan = fast_val < mid_val < slow_val

        ride_zone = self.ride_tolerance * current_atr

        if bullish_fan and rsi_val > self.rsi_long_threshold:
            if abs(price - fast_val) <= ride_zone and price >= fast_val:
                entry = price
                sl = entry - self.sl_atr_mult * current_atr
                tp = entry + self.tp_atr_mult * current_atr
                rr = abs(tp - entry) / abs(entry - sl) if abs(entry - sl) > 0 else 0
                confidence = self._calc_confidence(
                    rr, rsi_val, fast_val, mid_val, slow_val, price, ride_zone, current_atr
                )
                if confidence >= 0.60:
                    return SignalCandidate(
                        strategy_name=self.name,
                        direction=SignalDirection.LONG,
                        entry_price=entry,
                        stop_loss=sl,
                        take_profit=tp,
                        confidence=confidence,
                        reasoning=(
                            f"EMA fan-out bullish on {timeframe.value}: "
                            f"EMA{self.ema_fast}={fast_val:.2f} > EMA{self.ema_mid}={mid_val:.2f} > EMA{self.ema_slow}={slow_val:.2f}. "
                            f"Price riding EMA{self.ema_fast}. RSI={rsi_val:.1f}. RR={rr:.2f}."
                        ),
                        timeframe_bias=timeframe,
                        timeframe_entry=timeframe,
                        atr_value=current_atr,
                    )

        elif bearish_fan and rsi_val < self.rsi_short_threshold:
            if abs(price - fast_val) <= ride_zone and price <= fast_val:
                entry = price
                sl = entry + self.sl_atr_mult * current_atr
                tp = entry - self.tp_atr_mult * current_atr
                rr = abs(entry - tp) / abs(sl - entry) if abs(sl - entry) > 0 else 0
                confidence = self._calc_confidence(
                    rr, rsi_val, fast_val, mid_val, slow_val, price, ride_zone, current_atr
                )
                if confidence >= 0.60:
                    return SignalCandidate(
                        strategy_name=self.name,
                        direction=SignalDirection.SHORT,
                        entry_price=entry,
                        stop_loss=sl,
                        take_profit=tp,
                        confidence=confidence,
                        reasoning=(
                            f"EMA fan-out bearish on {timeframe.value}: "
                            f"EMA{self.ema_fast}={fast_val:.2f} < EMA{self.ema_mid}={mid_val:.2f} < EMA{self.ema_slow}={slow_val:.2f}. "
                            f"Price riding EMA{self.ema_fast}. RSI={rsi_val:.1f}. RR={rr:.2f}."
                        ),
                        timeframe_bias=timeframe,
                        timeframe_entry=timeframe,
                        atr_value=current_atr,
                    )

        return None

    def _calc_confidence(
        self,
        rr: float,
        rsi_val: float,
        fast: float,
        mid: float,
        slow: float,
        price: float,
        ride_zone: float,
        current_atr: float,
    ) -> float:
        score = 0.50

        # Reward/risk
        if rr >= 2.0:
            score += 0.15
        elif rr >= 1.5:
            score += 0.10

        # EMA spread quality — wider fan = stronger momentum
        if slow > 0:
            spread = abs(fast - slow) / slow
            if spread >= 0.005:
                score += 0.10
            elif spread >= 0.002:
                score += 0.05

        # RSI strength
        rsi_strength = abs(rsi_val - 50) / 50
        score += 0.05 * rsi_strength

        # Price riding precision
        if ride_zone > 0:
            distance = abs(price - fast)
            precision = 1 - (distance / ride_zone)
            score += 0.05 * max(precision, 0)

        return min(score, 1.0)
