"""Correlation analyzer — cross-asset correlation tracking for DXY and US10Y vs gold."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.repositories.correlations import CorrelationRepository

logger = logging.getLogger(__name__)

ROLLING_WINDOW = 20


@dataclass(frozen=True)
class CorrelationSummary:
    dxy_correlation: float  # rolling correlation of DXY vs gold
    us10y_correlation: float  # rolling correlation of US10Y vs gold
    directional_signal: str  # "bullish", "bearish", "neutral"
    reasoning: str


class CorrelationAnalyzer:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = CorrelationRepository(session)

    async def analyze(self, gold_prices: pd.Series | None = None) -> CorrelationSummary:
        """Compute rolling correlations of DXY and US10Y vs gold.

        Fetches recent data from the correlation_data table. If insufficient
        data, returns neutral with zero correlations.
        """
        dxy_rows = await self._repo.get_recent("DXY", limit=ROLLING_WINDOW + 10)
        us10y_rows = await self._repo.get_recent("US10Y", limit=ROLLING_WINDOW + 10)
        gold_rows = await self._repo.get_recent("XAU/USD", limit=ROLLING_WINDOW + 10)

        # Need at least ROLLING_WINDOW data points for meaningful correlation
        if len(dxy_rows) < ROLLING_WINDOW or len(gold_rows) < ROLLING_WINDOW:
            return CorrelationSummary(
                dxy_correlation=0.0,
                us10y_correlation=0.0,
                directional_signal="neutral",
                reasoning="Insufficient correlation data",
            )

        # Build aligned price series (sorted ascending by timestamp)
        gold_df = self._to_series(gold_rows)
        dxy_df = self._to_series(dxy_rows)
        us10y_df = self._to_series(us10y_rows) if len(us10y_rows) >= ROLLING_WINDOW else None

        # Compute rolling correlation over last ROLLING_WINDOW periods
        dxy_corr = self._rolling_correlation(gold_df, dxy_df)
        us10y_corr = self._rolling_correlation(gold_df, us10y_df) if us10y_df is not None else 0.0

        # Directional signal logic:
        # DXY falling + yields falling = gold bullish (classic safe-haven flow)
        # DXY rising + yields rising = gold bearish (risk-on / tightening)
        dxy_direction = self._recent_direction(dxy_df)
        us10y_direction = self._recent_direction(us10y_df) if us10y_df is not None else 0.0

        if dxy_direction < 0 and us10y_direction <= 0:
            signal = "bullish"
            reason = f"DXY falling ({dxy_direction:+.3f}) and yields flat/falling ({us10y_direction:+.3f}) — gold bullish"
        elif dxy_direction > 0 and us10y_direction >= 0:
            signal = "bearish"
            reason = f"DXY rising ({dxy_direction:+.3f}) and yields flat/rising ({us10y_direction:+.3f}) — gold bearish"
        else:
            signal = "neutral"
            reason = f"Mixed signals: DXY ({dxy_direction:+.3f}), yields ({us10y_direction:+.3f})"

        return CorrelationSummary(
            dxy_correlation=round(dxy_corr, 4),
            us10y_correlation=round(us10y_corr, 4),
            directional_signal=signal,
            reasoning=reason,
        )

    @staticmethod
    def _to_series(rows: list) -> pd.Series:
        """Convert DB rows to a price Series sorted ascending by timestamp."""
        data = [(r.timestamp, r.price) for r in rows]
        data.sort(key=lambda x: x[0])
        return pd.Series([p for _, p in data], index=[t for t, _ in data])

    @staticmethod
    def _rolling_correlation(series_a: pd.Series, series_b: pd.Series) -> float:
        """Compute the most recent rolling correlation coefficient."""
        # Align on common index (intersection of timestamps)
        aligned = pd.DataFrame({"a": series_a, "b": series_b}).dropna()
        if len(aligned) < ROLLING_WINDOW:
            return 0.0
        corr = aligned["a"].rolling(ROLLING_WINDOW).corr(aligned["b"])
        last_corr = corr.iloc[-1]
        return float(last_corr) if not np.isnan(last_corr) else 0.0

    @staticmethod
    def _recent_direction(series: pd.Series) -> float:
        """Compute recent directional change as percentage over last 5 periods."""
        if series is None or len(series) < 5:
            return 0.0
        recent = series.iloc[-5:]
        if recent.iloc[0] == 0:
            return 0.0
        return float((recent.iloc[-1] - recent.iloc[0]) / recent.iloc[0])
