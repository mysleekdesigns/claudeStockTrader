from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import pandas as pd

from backend.database.models import SignalDirection, Timeframe


@dataclass(frozen=True)
class SignalCandidate:
    strategy_name: str
    direction: SignalDirection
    entry_price: float
    stop_loss: float
    take_profit: float
    confidence: float
    reasoning: str
    timeframe_bias: Timeframe
    timeframe_entry: Timeframe
    atr_value: float


@runtime_checkable
class TradingStrategy(Protocol):
    name: str

    def evaluate(
        self,
        candles: dict[Timeframe, pd.DataFrame],
    ) -> list[SignalCandidate]:
        """Evaluate candle data and return zero or more signal candidates.

        Args:
            candles: Dict mapping Timeframe to a DataFrame with columns:
                     timestamp, open, high, low, close, volume
                     sorted by timestamp ascending.

        Returns:
            List of SignalCandidate with confidence >= 0.60.
        """
        ...
