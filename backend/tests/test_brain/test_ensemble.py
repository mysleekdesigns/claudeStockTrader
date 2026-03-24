"""Tests for ensemble decision maker."""

import json
from unittest.mock import AsyncMock

import pytest

from backend.brain.ensemble import (
    EnsembleDecisionMaker,
    EnsembleResult,
    _parse_analyst_response,
)

pytestmark = pytest.mark.asyncio


def _make_response(activated, suppressed=None, multiplier=1.0, reasoning="test"):
    return json.dumps({
        "activated_strategies": activated,
        "suppressed_strategies": suppressed or [],
        "position_size_multiplier": multiplier,
        "reasoning": reasoning,
    })


@pytest.fixture
def mock_claude_client():
    client = AsyncMock()
    return client


class TestParseAnalystResponse:
    def test_valid_json(self):
        resp = '{"activated_strategies": ["a"], "suppressed_strategies": [], "position_size_multiplier": 0.8, "reasoning": "ok"}'
        result = _parse_analyst_response(resp)
        assert result["activated_strategies"] == ["a"]

    def test_code_block(self):
        resp = '```json\n{"activated_strategies": ["b"], "suppressed_strategies": [], "position_size_multiplier": 1.0, "reasoning": "ok"}\n```'
        result = _parse_analyst_response(resp)
        assert result["activated_strategies"] == ["b"]

    def test_invalid_json(self):
        result = _parse_analyst_response("not json")
        assert result["activated_strategies"] == []


class TestEnsembleMajorityVote:
    async def test_2_of_3_agree_activates(self, mock_claude_client):
        # Conservative and Momentum agree on trend_continuation
        mock_claude_client.decide = AsyncMock(side_effect=[
            _make_response(["trend_continuation"], multiplier=0.7),
            _make_response(["trend_continuation", "ema_momentum"], multiplier=1.0),
            _make_response(["liquidity_sweep"], multiplier=0.8),
        ])
        ensemble = EnsembleDecisionMaker(mock_claude_client)
        result = await ensemble.decide("test prompt")

        assert "trend_continuation" in result.activated_strategies
        assert result.consensus is True
        assert len(result.individual_decisions) == 3

    async def test_all_agree(self, mock_claude_client):
        mock_claude_client.decide = AsyncMock(side_effect=[
            _make_response(["trend_continuation"]),
            _make_response(["trend_continuation"]),
            _make_response(["trend_continuation"]),
        ])
        ensemble = EnsembleDecisionMaker(mock_claude_client)
        result = await ensemble.decide("test prompt")

        assert "trend_continuation" in result.activated_strategies
        assert result.consensus is True

    async def test_all_disagree_suppresses(self, mock_claude_client):
        mock_claude_client.decide = AsyncMock(side_effect=[
            _make_response(["strategy_a"]),
            _make_response(["strategy_b"]),
            _make_response(["strategy_c"]),
        ])
        ensemble = EnsembleDecisionMaker(mock_claude_client)
        result = await ensemble.decide("test prompt")

        assert result.activated_strategies == []
        assert result.consensus is False
        assert "NO CONSENSUS" in result.reasoning

    async def test_no_consensus_reduces_position_size(self, mock_claude_client):
        mock_claude_client.decide = AsyncMock(side_effect=[
            _make_response(["a"], multiplier=1.0),
            _make_response(["b"], multiplier=1.0),
            _make_response(["c"], multiplier=1.0),
        ])
        ensemble = EnsembleDecisionMaker(mock_claude_client)
        result = await ensemble.decide("test prompt")

        # No consensus should reduce position size
        assert result.position_size_multiplier < 1.0

    async def test_conservative_weighted_heavier(self, mock_claude_client):
        # Conservative (1.5x weight) wants 0.5, others want 1.0
        mock_claude_client.decide = AsyncMock(side_effect=[
            _make_response(["a", "b"], multiplier=0.5),   # conservative: 1.5x weight
            _make_response(["a", "b"], multiplier=1.0),   # momentum: 1.0x weight
            _make_response(["a", "b"], multiplier=1.0),   # contrarian: 1.0x weight
        ])
        ensemble = EnsembleDecisionMaker(mock_claude_client)
        result = await ensemble.decide("test prompt")

        # Weighted avg: (0.5*1.5 + 1.0*1.0 + 1.0*1.0) / (1.5+1.0+1.0) = 2.75/3.5 ~= 0.79
        assert 0.70 < result.position_size_multiplier < 0.85

    async def test_handles_analyst_failure(self, mock_claude_client):
        mock_claude_client.decide = AsyncMock(side_effect=[
            _make_response(["trend_continuation"]),
            Exception("API error"),
            _make_response(["trend_continuation"]),
        ])
        ensemble = EnsembleDecisionMaker(mock_claude_client)
        result = await ensemble.decide("test prompt")

        assert "trend_continuation" in result.activated_strategies
        assert result.consensus is True
        # Should still have 3 decisions (one with error)
        assert len(result.individual_decisions) == 3
        assert "error" in result.individual_decisions[1]


class TestEnsembleResult:
    async def test_result_fields(self, mock_claude_client):
        mock_claude_client.decide = AsyncMock(side_effect=[
            _make_response(["a"], reasoning="conservative view"),
            _make_response(["a"], reasoning="momentum view"),
            _make_response(["b"], reasoning="contrarian view"),
        ])
        ensemble = EnsembleDecisionMaker(mock_claude_client)
        result = await ensemble.decide("test prompt")

        assert isinstance(result, EnsembleResult)
        assert isinstance(result.activated_strategies, list)
        assert isinstance(result.suppressed_strategies, list)
        assert isinstance(result.position_size_multiplier, float)
        assert isinstance(result.reasoning, str)
        assert isinstance(result.individual_decisions, list)
        assert isinstance(result.consensus, bool)
