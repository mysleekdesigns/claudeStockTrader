"""A/B Testing framework for decision pipeline variants."""

from __future__ import annotations

import logging
import random

from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.database.repositories.ab_tests import ABTestRepository

logger = logging.getLogger(__name__)

# Variant configs: each variant can modify the decision prompt or ensemble weights
VARIANT_CONFIGS: dict[str, dict] = {
    "baseline": {
        "system_prompt_suffix": "",
        "position_size_bias": 0.0,
        "strategy_weight_overrides": {},
    },
    "enhanced": {
        "system_prompt_suffix": (
            "\nAdditional instruction: Weight recent performance (last 7 days) "
            "more heavily than historical averages. Be more aggressive in high-momentum "
            "conditions and more conservative during ranging markets."
        ),
        "position_size_bias": 0.0,
        "strategy_weight_overrides": {},
    },
}


class ABTestManager:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = ABTestRepository(session)

    def assign_variant(self) -> str:
        """Randomly assign a variant for a decision cycle."""
        if not settings.ab_testing_enabled:
            return settings.ab_default_variant

        variants = settings.ab_variants
        if not variants:
            return settings.ab_default_variant

        return random.choice(variants)

    def get_variant_config(self, variant_name: str) -> dict:
        """Return prompt/ensemble config for the assigned variant."""
        return VARIANT_CONFIGS.get(variant_name, VARIANT_CONFIGS["baseline"])

    async def record_outcome(
        self,
        variant_name: str,
        decision_cycle_id: int,
        signals_created: int,
        signals_won: int = 0,
        signals_lost: int = 0,
    ) -> int:
        """Record the outcome of a decision cycle for a variant. Returns the run ID."""
        total = signals_won + signals_lost
        win_rate = signals_won / total if total > 0 else 0.0

        run = await self.repo.create({
            "variant_name": variant_name,
            "decision_cycle_id": decision_cycle_id,
            "signals_created": signals_created,
            "signals_won": signals_won,
            "signals_lost": signals_lost,
            "win_rate": win_rate,
        })
        logger.info(
            "A/B test recorded: variant=%s cycle=%d signals=%d",
            variant_name, decision_cycle_id, signals_created,
        )
        return run.id

    async def get_results(self) -> dict:
        """Get statistical comparison of variants using chi-squared test."""
        summaries = await self.repo.get_variant_summary()

        if len(summaries) < 2:
            return {
                "variants": summaries,
                "significant": False,
                "p_value": None,
                "recommendation": "Need at least 2 variants with data to compare.",
            }

        # Build variant result list
        variant_results = []
        observed = []
        for s in summaries:
            won = s["total_won"]
            lost = s["total_lost"]
            total = won + lost
            win_rate = won / total if total > 0 else 0.0
            variant_results.append({
                **s,
                "win_rate": win_rate,
            })
            observed.append([won, lost])

        # Chi-squared test for independence
        p_value = None
        significant = False
        try:
            from scipy.stats import chi2_contingency

            # Only run if we have enough data
            if all(sum(row) >= 10 for row in observed):
                chi2, p_value, dof, expected = chi2_contingency(observed)
                significant = p_value < 0.05
        except ImportError:
            # scipy not available — fall back to no significance test
            logger.warning("scipy not installed, skipping chi-squared test")
        except ValueError:
            # Not enough data for the test
            pass

        # Determine recommendation
        if not significant:
            recommendation = "No statistically significant difference between variants (p > 0.05)."
        else:
            best = max(variant_results, key=lambda v: v["win_rate"])
            recommendation = (
                f"Variant '{best['variant_name']}' shows significantly better performance "
                f"(win_rate={best['win_rate']:.1%}, p={p_value:.4f}). Consider adopting it."
            )

        return {
            "variants": variant_results,
            "significant": significant,
            "p_value": p_value,
            "recommendation": recommendation,
        }
