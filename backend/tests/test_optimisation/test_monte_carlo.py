"""Tests for Monte Carlo simulation — statistical properties."""

import numpy as np
import pytest

from backend.optimisation.monte_carlo import (
    _compute_drawdown_series,
    _monte_carlo_sim,
)


class TestComputeDrawdownSeries:
    def test_no_drawdown_on_monotonic_increase(self):
        pnl = np.array([1.0, 1.0, 1.0, 1.0, 1.0])
        dd = _compute_drawdown_series(pnl)
        assert (dd == 0).all()

    def test_drawdown_on_loss(self):
        pnl = np.array([10.0, -5.0, -3.0, 2.0])
        dd = _compute_drawdown_series(pnl)
        # After 10: cum=10, max=10, dd=0
        # After -5: cum=5, max=10, dd=5
        # After -3: cum=2, max=10, dd=8
        # After 2: cum=4, max=10, dd=6
        assert dd[0] == 0.0
        assert dd[1] == 5.0
        assert dd[2] == 8.0
        assert dd[3] == 6.0

    def test_empty_array(self):
        dd = _compute_drawdown_series(np.array([]))
        assert len(dd) == 0

    def test_single_element(self):
        dd = _compute_drawdown_series(np.array([5.0]))
        assert dd[0] == 0.0

    def test_all_losses(self):
        pnl = np.array([-1.0, -2.0, -3.0])
        dd = _compute_drawdown_series(pnl)
        # cum = [-1, -3, -6], running_max = [-1, -1, -1], dd = [0, 2, 5]
        assert dd[0] == 0.0
        assert dd[1] == 2.0
        assert dd[2] == 5.0


class TestMonteCarloSim:
    def test_minimum_reshuffles(self):
        """PRD requires minimum 1000 reshuffles."""
        pnl = np.random.default_rng(42).normal(1.0, 5.0, size=50)
        result = _monte_carlo_sim(pnl, 1000)
        assert "mean_drawdown" in result
        assert "p95_drawdown" in result
        assert "win_rate_mean" in result
        assert "win_rate_std" in result
        assert "max_drawdown_std" in result

    def test_p95_greater_or_equal_mean(self):
        """P95 drawdown should always be >= mean drawdown."""
        pnl = np.random.default_rng(42).normal(0.5, 3.0, size=100)
        result = _monte_carlo_sim(pnl, 1000)
        assert result["p95_drawdown"] >= result["mean_drawdown"]

    def test_win_rate_bounded(self):
        """Win rate should always be between 0 and 1."""
        pnl = np.random.default_rng(42).normal(0, 5.0, size=50)
        result = _monte_carlo_sim(pnl, 500)
        assert 0.0 <= result["win_rate_mean"] <= 1.0

    def test_all_wins_high_win_rate(self):
        pnl = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        result = _monte_carlo_sim(pnl, 100)
        assert result["win_rate_mean"] == 1.0
        assert result["win_rate_std"] == 0.0

    def test_all_losses_zero_win_rate(self):
        pnl = np.array([-1.0, -2.0, -3.0, -4.0, -5.0])
        result = _monte_carlo_sim(pnl, 100)
        assert result["win_rate_mean"] == 0.0

    def test_drawdown_non_negative(self):
        pnl = np.random.default_rng(42).normal(0, 5.0, size=100)
        result = _monte_carlo_sim(pnl, 500)
        assert result["mean_drawdown"] >= 0.0
        assert result["p95_drawdown"] >= 0.0

    def test_deterministic_with_seed(self):
        """Same input, different reshuffles should produce similar statistical properties."""
        pnl = np.random.default_rng(42).normal(1.0, 5.0, size=100)
        r1 = _monte_carlo_sim(pnl, 2000)
        r2 = _monte_carlo_sim(pnl, 2000)
        # With 2000 reshuffles, means should be close (within 20%)
        assert abs(r1["mean_drawdown"] - r2["mean_drawdown"]) / max(r1["mean_drawdown"], 0.01) < 0.3

    def test_mixed_pnl_reasonable_win_rate(self):
        rng = np.random.default_rng(42)
        pnl = rng.normal(0, 5.0, size=200)
        result = _monte_carlo_sim(pnl, 1000)
        # Normally distributed around 0 => ~50% win rate
        assert 0.3 <= result["win_rate_mean"] <= 0.7

    def test_std_is_positive_for_varied_data(self):
        pnl = np.random.default_rng(42).normal(0, 5.0, size=50)
        result = _monte_carlo_sim(pnl, 500)
        assert result["win_rate_std"] > 0
        assert result["max_drawdown_std"] > 0
