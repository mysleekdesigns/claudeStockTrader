from backend.strategies.base import SignalCandidate, TradingStrategy
from backend.strategies.breakout_expansion import BreakoutExpansionStrategy
from backend.strategies.ema_momentum import EMAMomentumStrategy
from backend.strategies.liquidity_sweep import LiquiditySweepStrategy
from backend.strategies.trend_continuation import TrendContinuationStrategy

ALL_STRATEGIES: list[TradingStrategy] = [
    LiquiditySweepStrategy(),
    TrendContinuationStrategy(),
    BreakoutExpansionStrategy(),
    EMAMomentumStrategy(),
]

__all__ = [
    "ALL_STRATEGIES",
    "BreakoutExpansionStrategy",
    "EMAMomentumStrategy",
    "LiquiditySweepStrategy",
    "SignalCandidate",
    "TradingStrategy",
    "TrendContinuationStrategy",
]
