"""Enhanced confidence scoring — post-processing bonuses for signal candidates."""

from __future__ import annotations

from backend.brain.correlations import CorrelationSummary
from backend.brain.market_regime import MarketRegime, RegimeResult
from backend.brain.session_filter import DEFAULT_WEIGHTS, SessionInfo
from backend.database.models import SignalDirection, Timeframe
from backend.strategies.base import SignalCandidate


def apply_confidence_bonuses(
    candidate: SignalCandidate,
    regime: RegimeResult | None = None,
    session_info: SessionInfo | None = None,
    correlation: CorrelationSummary | None = None,
    recent_win_rate: float | None = None,
) -> SignalCandidate:
    """Apply post-processing confidence bonuses to a signal candidate.

    Bonuses:
    - Regime alignment (+0.10): signal direction matches detected regime
    - Session bonus (+0.05): strategy historically strong in current session
    - Correlation confirmation (+0.10): cross-asset data confirms direction
    - Feedback bonus (+0.05): strategy winning recently (last 10 signals >60% WR)

    Returns a new SignalCandidate with updated confidence (capped at 1.0).
    """
    bonus = 0.0

    # Regime alignment: +0.10
    if regime is not None:
        if (
            candidate.direction == SignalDirection.LONG
            and regime.regime == MarketRegime.TRENDING_UP
        ) or (
            candidate.direction == SignalDirection.SHORT
            and regime.regime == MarketRegime.TRENDING_DOWN
        ):
            bonus += 0.10

    # Session bonus: +0.05 if strategy weight >= 0.8 in current session
    if session_info is not None:
        weight = session_info.strategy_weights.get(candidate.strategy_name, 0.5)
        if weight >= 0.8:
            bonus += 0.05

    # Correlation confirmation: +0.10
    if correlation is not None:
        if (
            candidate.direction == SignalDirection.LONG
            and correlation.directional_signal == "bullish"
        ) or (
            candidate.direction == SignalDirection.SHORT
            and correlation.directional_signal == "bearish"
        ):
            bonus += 0.10

    # Feedback bonus: +0.05 if recent win rate > 60%
    if recent_win_rate is not None and recent_win_rate > 0.60:
        bonus += 0.05

    if bonus == 0.0:
        return candidate

    new_confidence = min(candidate.confidence + bonus, 1.0)
    return SignalCandidate(
        strategy_name=candidate.strategy_name,
        direction=candidate.direction,
        entry_price=candidate.entry_price,
        stop_loss=candidate.stop_loss,
        take_profit=candidate.take_profit,
        confidence=new_confidence,
        reasoning=candidate.reasoning,
        timeframe_bias=candidate.timeframe_bias,
        timeframe_entry=candidate.timeframe_entry,
        atr_value=candidate.atr_value,
    )


def compute_recent_win_rate(
    resolved_signals: list,
    strategy_name: str,
    count: int = 10,
) -> float | None:
    """Compute win rate from the last `count` resolved signals for a strategy.

    Returns None if fewer than 3 resolved signals exist.
    """
    strategy_signals = [
        s for s in resolved_signals
        if s.strategy_name == strategy_name and s.status.value in ("won", "lost")
    ]
    if len(strategy_signals) < 3:
        return None

    recent = strategy_signals[:count]  # already sorted desc by created_at
    wins = sum(1 for s in recent if s.status.value == "won")
    return wins / len(recent)
