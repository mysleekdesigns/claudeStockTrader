"""Tests for the decision pipeline."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pandas as pd
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from backend.brain.decision_pipeline import (
    _compute_composite_score,
    _parse_claude_response,
    _summarise_candles,
    run_decision_pipeline,
)
from backend.database.models import (
    Candle,
    RiskState,
    SignalDirection,
    SignalStatus,
    StrategyPerformance,
    Timeframe,
)

pytestmark = pytest.mark.asyncio


class TestParseClaudeResponse:
    def test_valid_json(self):
        resp = '{"activated_strategies": ["a"], "suppressed_strategies": [], "position_size_multiplier": 0.8, "reasoning": "test"}'
        result = _parse_claude_response(resp)
        assert result["activated_strategies"] == ["a"]
        assert result["position_size_multiplier"] == 0.8

    def test_json_in_code_block(self):
        resp = '```json\n{"activated_strategies": ["b"], "suppressed_strategies": [], "position_size_multiplier": 1.0, "reasoning": "x"}\n```'
        result = _parse_claude_response(resp)
        assert result["activated_strategies"] == ["b"]

    def test_invalid_json_returns_defaults(self):
        result = _parse_claude_response("this is not json")
        assert result["activated_strategies"] == []
        assert result["position_size_multiplier"] == 1.0

    def test_empty_string(self):
        result = _parse_claude_response("")
        assert result["activated_strategies"] == []


class TestCompositeScore:
    def test_basic_computation(self):
        perf = MagicMock()
        perf.win_rate = 0.65
        perf.avg_rr = 2.0
        perf.max_drawdown = 0.10
        score = _compute_composite_score(perf)
        expected = 0.65 * 2.0 * (1.0 - 0.10)
        assert abs(score - expected) < 1e-6

    def test_zero_drawdown(self):
        perf = MagicMock()
        perf.win_rate = 0.70
        perf.avg_rr = 1.5
        perf.max_drawdown = 0.0
        score = _compute_composite_score(perf)
        assert score == 0.70 * 1.5

    def test_full_drawdown(self):
        perf = MagicMock()
        perf.win_rate = 0.70
        perf.avg_rr = 1.5
        perf.max_drawdown = 1.0
        score = _compute_composite_score(perf)
        assert score == 0.0


class TestSummariseCandles:
    def test_summarises_all_timeframes(self):
        dfs = {}
        for tf in [Timeframe.D1, Timeframe.H4, Timeframe.H1, Timeframe.M15]:
            dfs[tf] = pd.DataFrame({
                "close": [2350.0, 2355.0],
                "high": [2360.0, 2365.0],
                "low": [2340.0, 2345.0],
            })
        summary = _summarise_candles(dfs)
        assert "1h" in summary
        assert "4h" in summary
        assert "close=" in summary

    def test_handles_empty_dict(self):
        assert _summarise_candles({}) == ""


class TestRunDecisionPipeline:
    async def test_cold_start_activates_all(
        self, session: AsyncSession, mock_redis, mock_claude_client
    ):
        """With no performance data and no candles, pipeline returns 0 signals."""
        # Need a risk state
        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        state = RiskState(
            date=today, daily_loss_pct=0.0, consecutive_stops=0, is_shutdown=False
        )
        session.add(state)
        await session.commit()

        count = await run_decision_pipeline(session, mock_redis, mock_claude_client)
        # No candle data => pipeline returns 0
        assert count == 0

    async def test_aborts_when_risk_shutdown(
        self, session: AsyncSession, mock_redis, mock_claude_client
    ):
        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        state = RiskState(
            date=today, daily_loss_pct=0.03, consecutive_stops=0,
            is_shutdown=True, shutdown_until=datetime.now(timezone.utc) + timedelta(hours=12),
        )
        session.add(state)
        await session.commit()

        count = await run_decision_pipeline(session, mock_redis, mock_claude_client)
        assert count == 0
        # Claude should NOT have been called
        mock_claude_client.decide.assert_not_called()
