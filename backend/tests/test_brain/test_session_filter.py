"""Tests for trading session filter."""

from datetime import datetime, timezone

import pytest

from backend.brain.session_filter import (
    SessionFilter,
    SessionInfo,
    TradingSession,
)


@pytest.fixture
def session_filter() -> SessionFilter:
    return SessionFilter()


class TestSessionClassification:
    def test_asian_session(self, session_filter):
        utc_3am = datetime(2026, 3, 24, 3, 0, tzinfo=timezone.utc)
        info = session_filter.get_current_session(utc_3am)
        assert info.session == TradingSession.ASIAN

    def test_london_session(self, session_filter):
        utc_10am = datetime(2026, 3, 24, 10, 0, tzinfo=timezone.utc)
        info = session_filter.get_current_session(utc_10am)
        assert info.session == TradingSession.LONDON

    def test_new_york_session(self, session_filter):
        utc_2pm = datetime(2026, 3, 24, 14, 0, tzinfo=timezone.utc)
        info = session_filter.get_current_session(utc_2pm)
        assert info.session == TradingSession.NEW_YORK

    def test_off_hours(self, session_filter):
        utc_22 = datetime(2026, 3, 24, 22, 0, tzinfo=timezone.utc)
        info = session_filter.get_current_session(utc_22)
        assert info.session == TradingSession.OFF_HOURS

    def test_london_ny_overlap_prefers_ny(self, session_filter):
        utc_1pm = datetime(2026, 3, 24, 13, 0, tzinfo=timezone.utc)
        info = session_filter.get_current_session(utc_1pm)
        assert info.session == TradingSession.NEW_YORK

    def test_midnight_is_asian(self, session_filter):
        utc_0 = datetime(2026, 3, 24, 0, 0, tzinfo=timezone.utc)
        info = session_filter.get_current_session(utc_0)
        assert info.session == TradingSession.ASIAN


class TestSessionWeights:
    def test_asian_favors_breakout(self, session_filter):
        utc_3am = datetime(2026, 3, 24, 3, 0, tzinfo=timezone.utc)
        info = session_filter.get_current_session(utc_3am)
        assert info.strategy_weights["breakout_expansion"] == 1.0
        assert info.strategy_weights["liquidity_sweep"] < 1.0

    def test_london_favors_trend_and_liquidity(self, session_filter):
        utc_10am = datetime(2026, 3, 24, 10, 0, tzinfo=timezone.utc)
        info = session_filter.get_current_session(utc_10am)
        assert info.strategy_weights["trend_continuation"] == 1.0
        assert info.strategy_weights["liquidity_sweep"] == 1.0

    def test_ny_all_active(self, session_filter):
        utc_2pm = datetime(2026, 3, 24, 14, 0, tzinfo=timezone.utc)
        info = session_filter.get_current_session(utc_2pm)
        for weight in info.strategy_weights.values():
            assert weight == 1.0

    def test_off_hours_reduced_multiplier(self, session_filter):
        utc_22 = datetime(2026, 3, 24, 22, 0, tzinfo=timezone.utc)
        info = session_filter.get_current_session(utc_22)
        assert info.position_size_multiplier == 0.5


class TestFormatForPrompt:
    def test_contains_session_name(self, session_filter):
        utc_3am = datetime(2026, 3, 24, 3, 0, tzinfo=timezone.utc)
        info = session_filter.get_current_session(utc_3am)
        text = session_filter.format_for_prompt(info)
        assert "Asian" in text
        assert "Position size multiplier" in text
        assert "Strategy weights" in text

    def test_default_now(self, session_filter):
        info = session_filter.get_current_session()
        assert isinstance(info, SessionInfo)
        assert info.session in TradingSession
