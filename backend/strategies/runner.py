"""Strategy runner — loads candle data and evaluates all strategies."""

from __future__ import annotations

import logging

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.database.models import Timeframe
from backend.database.repositories.candles import CandleRepository
from backend.database.repositories.signals import SignalRepository
from backend.strategies import ALL_STRATEGIES
from backend.strategies.base import SignalCandidate

logger = logging.getLogger(__name__)

SYMBOL = "XAU/USD"
CANDLE_LIMITS = {
    Timeframe.M15: 500,
    Timeframe.H1: 300,
    Timeframe.H4: 250,
    Timeframe.D1: 250,
}


async def run_all_strategies(session: AsyncSession) -> int:
    """Run all strategies against current candle data.

    Returns the number of signals created.
    """
    candle_repo = CandleRepository(session)
    signal_repo = SignalRepository(session)

    # Load candle data for all timeframes
    candles: dict[Timeframe, pd.DataFrame] = {}
    for tf, limit in CANDLE_LIMITS.items():
        rows = await candle_repo.get_range(symbol=SYMBOL, timeframe=tf, limit=limit)
        if not rows:
            continue
        # Convert to DataFrame sorted ascending by timestamp
        data = [
            {
                "timestamp": r.timestamp,
                "open": r.open,
                "high": r.high,
                "low": r.low,
                "close": r.close,
                "volume": r.volume,
            }
            for r in sorted(rows, key=lambda c: c.timestamp)
        ]
        candles[tf] = pd.DataFrame(data)

    if not candles:
        logger.warning("No candle data available for strategy evaluation")
        return 0

    # Run each strategy
    created = 0
    for strategy in ALL_STRATEGIES:
        try:
            candidates = strategy.evaluate(candles)
            for candidate in candidates:
                if candidate.confidence < settings.min_signal_confidence:
                    continue
                await signal_repo.create(
                    {
                        "strategy_name": candidate.strategy_name,
                        "direction": candidate.direction,
                        "entry_price": candidate.entry_price,
                        "stop_loss": candidate.stop_loss,
                        "take_profit": candidate.take_profit,
                        "confidence_score": candidate.confidence,
                        "reasoning": candidate.reasoning,
                    }
                )
                created += 1
                logger.info(
                    "Signal created: %s %s @ %.2f (conf=%.2f)",
                    candidate.strategy_name,
                    candidate.direction.value,
                    candidate.entry_price,
                    candidate.confidence,
                )
        except Exception:
            logger.exception("Strategy %s failed", strategy.name)

    return created
