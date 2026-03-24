"""Tests for the A/B testing framework."""

from __future__ import annotations

from unittest.mock import patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from backend.brain.ab_testing import ABTestManager
from backend.database.models import ABTestRun
from backend.database.repositories.ab_tests import ABTestRepository


class TestABTestManager:
    """Tests for ABTestManager."""

    async def test_assign_variant_disabled(self, session: AsyncSession):
        """When AB testing is disabled, returns default variant."""
        manager = ABTestManager(session)
        with patch("backend.brain.ab_testing.settings") as mock_settings:
            mock_settings.ab_testing_enabled = False
            mock_settings.ab_default_variant = "baseline"
            variant = manager.assign_variant()
        assert variant == "baseline"

    async def test_assign_variant_enabled(self, session: AsyncSession):
        """When AB testing is enabled, returns one of the configured variants."""
        manager = ABTestManager(session)
        with patch("backend.brain.ab_testing.settings") as mock_settings:
            mock_settings.ab_testing_enabled = True
            mock_settings.ab_variants = ["baseline", "enhanced"]
            mock_settings.ab_default_variant = "baseline"
            variant = manager.assign_variant()
        assert variant in ["baseline", "enhanced"]

    async def test_assign_variant_empty_list(self, session: AsyncSession):
        """When variant list is empty, returns default."""
        manager = ABTestManager(session)
        with patch("backend.brain.ab_testing.settings") as mock_settings:
            mock_settings.ab_testing_enabled = True
            mock_settings.ab_variants = []
            mock_settings.ab_default_variant = "baseline"
            variant = manager.assign_variant()
        assert variant == "baseline"

    async def test_get_variant_config_known(self, session: AsyncSession):
        """Known variant returns its config."""
        manager = ABTestManager(session)
        config = manager.get_variant_config("baseline")
        assert "system_prompt_suffix" in config
        assert config["system_prompt_suffix"] == ""

    async def test_get_variant_config_enhanced(self, session: AsyncSession):
        """Enhanced variant has a non-empty prompt suffix."""
        manager = ABTestManager(session)
        config = manager.get_variant_config("enhanced")
        assert len(config["system_prompt_suffix"]) > 0

    async def test_get_variant_config_unknown(self, session: AsyncSession):
        """Unknown variant falls back to baseline config."""
        manager = ABTestManager(session)
        config = manager.get_variant_config("nonexistent")
        assert config["system_prompt_suffix"] == ""

    async def test_record_outcome(self, session: AsyncSession):
        """Recording an outcome creates a DB row."""
        manager = ABTestManager(session)
        run_id = await manager.record_outcome(
            variant_name="baseline",
            decision_cycle_id=1,
            signals_created=5,
            signals_won=3,
            signals_lost=2,
        )
        assert run_id > 0

        # Verify in DB
        repo = ABTestRepository(session)
        run = await repo.get_by_decision_cycle(1)
        assert run is not None
        assert run.variant_name == "baseline"
        assert run.signals_created == 5
        assert run.signals_won == 3
        assert run.signals_lost == 2
        assert run.win_rate == pytest.approx(0.6)

    async def test_record_outcome_zero_resolved(self, session: AsyncSession):
        """Win rate is 0 when no signals resolved."""
        manager = ABTestManager(session)
        run_id = await manager.record_outcome(
            variant_name="enhanced",
            decision_cycle_id=2,
            signals_created=3,
        )
        repo = ABTestRepository(session)
        run = await repo.get_by_decision_cycle(2)
        assert run is not None
        assert run.win_rate == 0.0

    async def test_get_results_no_data(self, session: AsyncSession):
        """Results with no data returns not significant."""
        manager = ABTestManager(session)
        results = await manager.get_results()
        assert results["significant"] is False
        assert results["p_value"] is None

    async def test_get_results_single_variant(self, session: AsyncSession):
        """Results with only one variant cannot compare."""
        manager = ABTestManager(session)
        await manager.record_outcome("baseline", 1, 10, 7, 3)
        results = await manager.get_results()
        assert results["significant"] is False
        assert "Need at least 2 variants" in results["recommendation"]

    async def test_get_results_two_variants(self, session: AsyncSession):
        """Results with two variants returns comparison."""
        manager = ABTestManager(session)
        # Record enough data for both variants
        for i in range(20):
            await manager.record_outcome("baseline", 100 + i, 5, 2, 3)
            await manager.record_outcome("enhanced", 200 + i, 5, 4, 1)

        results = await manager.get_results()
        assert len(results["variants"]) == 2
        assert results["p_value"] is not None or "recommendation" in results

        # Enhanced should have higher win rate
        variant_rates = {
            v["variant_name"]: v["win_rate"] for v in results["variants"]
        }
        assert variant_rates["enhanced"] > variant_rates["baseline"]


class TestABTestRepository:
    """Tests for ABTestRepository CRUD."""

    async def test_create_and_get(self, session: AsyncSession):
        repo = ABTestRepository(session)
        run = await repo.create({
            "variant_name": "baseline",
            "decision_cycle_id": 42,
            "signals_created": 3,
            "signals_won": 1,
            "signals_lost": 1,
            "win_rate": 0.5,
        })
        assert run.id is not None
        assert run.variant_name == "baseline"

        fetched = await repo.get_by_decision_cycle(42)
        assert fetched is not None
        assert fetched.id == run.id

    async def test_update_outcomes(self, session: AsyncSession):
        repo = ABTestRepository(session)
        run = await repo.create({
            "variant_name": "enhanced",
            "decision_cycle_id": 99,
            "signals_created": 5,
        })
        updated = await repo.update_outcomes(run.id, signals_won=4, signals_lost=1)
        assert updated is not None
        assert updated.signals_won == 4
        assert updated.signals_lost == 1
        assert updated.win_rate == pytest.approx(0.8)

    async def test_update_outcomes_nonexistent(self, session: AsyncSession):
        repo = ABTestRepository(session)
        result = await repo.update_outcomes(9999, signals_won=1, signals_lost=0)
        assert result is None

    async def test_list_recent(self, session: AsyncSession):
        repo = ABTestRepository(session)
        for i in range(5):
            await repo.create({
                "variant_name": "baseline",
                "decision_cycle_id": i,
                "signals_created": i,
            })
        runs = await repo.list_recent(limit=3)
        assert len(runs) == 3

    async def test_variant_summary(self, session: AsyncSession):
        repo = ABTestRepository(session)
        await repo.create({"variant_name": "a", "decision_cycle_id": 1, "signals_created": 5, "signals_won": 3, "signals_lost": 2})
        await repo.create({"variant_name": "a", "decision_cycle_id": 2, "signals_created": 3, "signals_won": 2, "signals_lost": 1})
        await repo.create({"variant_name": "b", "decision_cycle_id": 3, "signals_created": 4, "signals_won": 1, "signals_lost": 3})

        summary = await repo.get_variant_summary()
        assert len(summary) == 2

        by_name = {s["variant_name"]: s for s in summary}
        assert by_name["a"]["total_cycles"] == 2
        assert by_name["a"]["total_won"] == 5
        assert by_name["b"]["total_lost"] == 3
