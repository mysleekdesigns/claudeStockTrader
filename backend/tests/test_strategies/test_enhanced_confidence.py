"""Tests for enhanced confidence scoring."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from backend.brain.correlations import CorrelationSummary
from backend.brain.market_regime import MarketRegime, RegimeResult
from backend.brain.session_filter import SessionInfo, TradingSession
from backend.database.models import SignalDirection, Timeframe
from backend.strategies.base import SignalCandidate
from backend.strategies.confidence import apply_confidence_bonuses, compute_recent_win_rate


def _make_candidate(
    direction: SignalDirection = SignalDirection.LONG,
    confidence: float = 0.70,
    strategy_name: str = "liquidity_sweep",
) -> SignalCandidate:
    return SignalCandidate(
        strategy_name=strategy_name,
        direction=direction,
        entry_price=2350.0,
        stop_loss=2330.0,
        take_profit=2390.0,
        confidence=confidence,
        reasoning="Test signal",
        timeframe_bias=Timeframe.H1,
        timeframe_entry=Timeframe.M15,
        atr_value=10.0,
    )


class TestApplyConfidenceBonuses:
    def test_no_bonuses_returns_same_confidence(self):
        candidate = _make_candidate()
        result = apply_confidence_bonuses(candidate)
        assert result.confidence == 0.70

    def test_regime_alignment_long_trending_up(self):
        candidate = _make_candidate(direction=SignalDirection.LONG)
        regime = RegimeResult(
            regime=MarketRegime.TRENDING_UP,
            confidence=0.8, adx_value=30.0, atr_ratio=1.2,
        )
        result = apply_confidence_bonuses(candidate, regime=regime)
        assert result.confidence == pytest.approx(0.80)  # +0.10

    def test_regime_alignment_short_trending_down(self):
        candidate = _make_candidate(direction=SignalDirection.SHORT)
        regime = RegimeResult(
            regime=MarketRegime.TRENDING_DOWN,
            confidence=0.8, adx_value=30.0, atr_ratio=1.2,
        )
        result = apply_confidence_bonuses(candidate, regime=regime)
        assert result.confidence == pytest.approx(0.80)  # +0.10

    def test_no_regime_bonus_when_misaligned(self):
        candidate = _make_candidate(direction=SignalDirection.LONG)
        regime = RegimeResult(
            regime=MarketRegime.TRENDING_DOWN,
            confidence=0.8, adx_value=30.0, atr_ratio=1.2,
        )
        result = apply_confidence_bonuses(candidate, regime=regime)
        assert result.confidence == 0.70  # no bonus

    def test_session_bonus_high_weight(self):
        candidate = _make_candidate(strategy_name="liquidity_sweep")
        session_info = SessionInfo(
            session=TradingSession.NEW_YORK,
            strategy_weights={"liquidity_sweep": 1.0},
            position_size_multiplier=1.0,
        )
        result = apply_confidence_bonuses(candidate, session_info=session_info)
        assert result.confidence == pytest.approx(0.75)  # +0.05

    def test_no_session_bonus_low_weight(self):
        candidate = _make_candidate(strategy_name="liquidity_sweep")
        session_info = SessionInfo(
            session=TradingSession.ASIAN,
            strategy_weights={"liquidity_sweep": 0.3},
            position_size_multiplier=0.8,
        )
        result = apply_confidence_bonuses(candidate, session_info=session_info)
        assert result.confidence == 0.70

    def test_correlation_confirmation_bullish(self):
        candidate = _make_candidate(direction=SignalDirection.LONG)
        correlation = CorrelationSummary(
            dxy_correlation=-0.5,
            us10y_correlation=-0.3,
            directional_signal="bullish",
            reasoning="DXY falling",
        )
        result = apply_confidence_bonuses(candidate, correlation=correlation)
        assert result.confidence == pytest.approx(0.80)  # +0.10

    def test_no_correlation_bonus_when_misaligned(self):
        candidate = _make_candidate(direction=SignalDirection.LONG)
        correlation = CorrelationSummary(
            dxy_correlation=0.5,
            us10y_correlation=0.3,
            directional_signal="bearish",
            reasoning="DXY rising",
        )
        result = apply_confidence_bonuses(candidate, correlation=correlation)
        assert result.confidence == 0.70

    def test_feedback_bonus_high_win_rate(self):
        candidate = _make_candidate()
        result = apply_confidence_bonuses(candidate, recent_win_rate=0.75)
        assert result.confidence == pytest.approx(0.75)  # +0.05

    def test_no_feedback_bonus_low_win_rate(self):
        candidate = _make_candidate()
        result = apply_confidence_bonuses(candidate, recent_win_rate=0.50)
        assert result.confidence == 0.70

    def test_all_bonuses_stacked(self):
        candidate = _make_candidate(direction=SignalDirection.LONG, confidence=0.70)
        regime = RegimeResult(
            regime=MarketRegime.TRENDING_UP,
            confidence=0.8, adx_value=30.0, atr_ratio=1.2,
        )
        session_info = SessionInfo(
            session=TradingSession.NEW_YORK,
            strategy_weights={"liquidity_sweep": 1.0},
            position_size_multiplier=1.0,
        )
        correlation = CorrelationSummary(
            dxy_correlation=-0.5,
            us10y_correlation=-0.3,
            directional_signal="bullish",
            reasoning="DXY falling",
        )
        result = apply_confidence_bonuses(
            candidate,
            regime=regime,
            session_info=session_info,
            correlation=correlation,
            recent_win_rate=0.80,
        )
        # +0.10 + 0.05 + 0.10 + 0.05 = +0.30 -> 1.0 (capped)
        assert result.confidence == pytest.approx(1.0)

    def test_confidence_capped_at_1(self):
        candidate = _make_candidate(confidence=0.95)
        regime = RegimeResult(
            regime=MarketRegime.TRENDING_UP,
            confidence=0.8, adx_value=30.0, atr_ratio=1.2,
        )
        result = apply_confidence_bonuses(candidate, regime=regime)
        assert result.confidence == 1.0  # capped

    def test_immutability_of_original(self):
        candidate = _make_candidate()
        result = apply_confidence_bonuses(candidate, recent_win_rate=0.80)
        assert candidate.confidence == 0.70  # original unchanged
        assert result.confidence == 0.75


class TestComputeRecentWinRate:
    def _make_signal(self, strategy: str, status: str):
        s = MagicMock()
        s.strategy_name = strategy
        s.status = MagicMock()
        s.status.value = status
        return s

    def test_returns_none_with_few_signals(self):
        signals = [self._make_signal("liquidity_sweep", "won")]
        assert compute_recent_win_rate(signals, "liquidity_sweep") is None

    def test_computes_win_rate(self):
        signals = [
            self._make_signal("liquidity_sweep", "won"),
            self._make_signal("liquidity_sweep", "won"),
            self._make_signal("liquidity_sweep", "lost"),
            self._make_signal("liquidity_sweep", "won"),
            self._make_signal("liquidity_sweep", "lost"),
        ]
        rate = compute_recent_win_rate(signals, "liquidity_sweep")
        assert rate == pytest.approx(0.6)

    def test_filters_by_strategy_name(self):
        signals = [
            self._make_signal("liquidity_sweep", "won"),
            self._make_signal("ema_momentum", "lost"),
            self._make_signal("liquidity_sweep", "won"),
            self._make_signal("liquidity_sweep", "won"),
        ]
        rate = compute_recent_win_rate(signals, "liquidity_sweep")
        assert rate == pytest.approx(1.0)

    def test_ignores_non_resolved_statuses(self):
        signals = [
            self._make_signal("liquidity_sweep", "won"),
            self._make_signal("liquidity_sweep", "pending"),
            self._make_signal("liquidity_sweep", "lost"),
            self._make_signal("liquidity_sweep", "won"),
        ]
        rate = compute_recent_win_rate(signals, "liquidity_sweep")
        assert rate == pytest.approx(2 / 3)
