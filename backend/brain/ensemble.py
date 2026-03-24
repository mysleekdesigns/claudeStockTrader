"""Ensemble decision maker — 3 parallel Claude analysts with majority vote."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass

from backend.brain.claude_client import ClaudeClient, RateLimitExceeded

logger = logging.getLogger(__name__)

CONSERVATIVE_SYSTEM = """You are a Conservative Gold Analyst focused on capital preservation.
Evaluate XAU/USD trading signals with these priorities:
- Protect capital above all — prefer tighter stop losses
- Only activate strategies with strong historical performance
- Reduce position sizes in uncertain conditions
- Be skeptical of signals in volatile or unclear regimes

Respond with ONLY valid JSON:
{
    "activated_strategies": ["strategy_name"],
    "suppressed_strategies": ["strategy_name"],
    "position_size_multiplier": 0.5,
    "reasoning": "Brief explanation"
}
position_size_multiplier must be between 0.25 and 1.0."""

MOMENTUM_SYSTEM = """You are a Momentum Gold Trader focused on trend strength.
Evaluate XAU/USD trading signals with these priorities:
- Capitalize on strong trends — favor trend_continuation and ema_momentum
- Use wider trailing stops to let winners run
- Increase position sizes when ADX confirms strong trends
- Reduce exposure in ranging/low-ADX markets

Respond with ONLY valid JSON:
{
    "activated_strategies": ["strategy_name"],
    "suppressed_strategies": ["strategy_name"],
    "position_size_multiplier": 1.0,
    "reasoning": "Brief explanation"
}
position_size_multiplier must be between 0.25 and 1.0."""

CONTRARIAN_SYSTEM = """You are a Contrarian Gold Analyst focused on mean reversion.
Evaluate XAU/USD trading signals with these priorities:
- Look for exhaustion signals — overextended moves likely to revert
- Favor liquidity_sweep and breakout_expansion at extremes
- Be cautious of chasing trends late — watch for divergences
- Reduce exposure when momentum is strong and trend is fresh

Respond with ONLY valid JSON:
{
    "activated_strategies": ["strategy_name"],
    "suppressed_strategies": ["strategy_name"],
    "position_size_multiplier": 0.75,
    "reasoning": "Brief explanation"
}
position_size_multiplier must be between 0.25 and 1.0."""

ANALYST_CONFIGS = [
    ("conservative", CONSERVATIVE_SYSTEM, 1.5),
    ("momentum", MOMENTUM_SYSTEM, 1.0),
    ("contrarian", CONTRARIAN_SYSTEM, 1.0),
]


@dataclass
class EnsembleResult:
    activated_strategies: list[str]
    suppressed_strategies: list[str]
    position_size_multiplier: float
    reasoning: str
    individual_decisions: list[dict]
    consensus: bool  # True if at least 2/3 agree on at least one strategy


class EnsembleDecisionMaker:
    """Run 3 parallel Claude calls and aggregate via majority vote."""

    def __init__(self, claude_client: ClaudeClient) -> None:
        self._client = claude_client

    async def decide(self, user_prompt: str) -> EnsembleResult:
        tasks = [
            self._call_analyst(name, system, user_prompt)
            for name, system, _ in ANALYST_CONFIGS
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        decisions: list[dict] = []
        for i, result in enumerate(results):
            name = ANALYST_CONFIGS[i][0]
            if isinstance(result, Exception):
                logger.warning("Analyst %s failed: %s", name, result)
                decisions.append({
                    "analyst": name,
                    "error": str(result),
                    "activated_strategies": [],
                    "suppressed_strategies": [],
                    "position_size_multiplier": 1.0,
                    "reasoning": f"Analyst {name} failed",
                })
            else:
                result["analyst"] = name
                decisions.append(result)

        return self._aggregate(decisions)

    async def _call_analyst(
        self, name: str, system: str, user_prompt: str
    ) -> dict:
        response_text = await self._client.decide(system, user_prompt)
        return _parse_analyst_response(response_text)

    def _aggregate(self, decisions: list[dict]) -> EnsembleResult:
        # Count strategy activations
        activation_counts: dict[str, int] = {}
        suppression_counts: dict[str, int] = {}
        valid_decisions = [d for d in decisions if "error" not in d]

        for d in valid_decisions:
            for s in d.get("activated_strategies", []):
                activation_counts[s] = activation_counts.get(s, 0) + 1
            for s in d.get("suppressed_strategies", []):
                suppression_counts[s] = suppression_counts.get(s, 0) + 1

        # Majority vote: strategy activated if 2/3 agree
        activated = [s for s, count in activation_counts.items() if count >= 2]
        suppressed = [
            s for s, count in suppression_counts.items()
            if count >= 2 and s not in activated
        ]

        # All 3 disagree (no strategy gets 2+ votes) -> suppress all
        consensus = len(activated) > 0
        if not consensus:
            activated = []
            suppressed = list(activation_counts.keys())

        # Weighted average position size (conservative gets 1.5x weight)
        total_weight = 0.0
        weighted_size = 0.0
        for i, d in enumerate(decisions):
            if "error" in d:
                continue
            weight = ANALYST_CONFIGS[i][2]
            size = max(0.25, min(1.0, d.get("position_size_multiplier", 1.0)))
            weighted_size += size * weight
            total_weight += weight

        position_size = weighted_size / total_weight if total_weight > 0 else 0.5
        if not consensus:
            position_size *= 0.5  # Further reduce when no consensus

        position_size = max(0.25, min(1.0, position_size))

        # Build reasoning
        reasoning_parts = []
        for d in decisions:
            analyst = d.get("analyst", "unknown")
            r = d.get("reasoning", "no reasoning")
            reasoning_parts.append(f"[{analyst}] {r}")

        consensus_note = "CONSENSUS" if consensus else "NO CONSENSUS - all strategies suppressed"
        reasoning = f"{consensus_note}. " + " | ".join(reasoning_parts)

        return EnsembleResult(
            activated_strategies=activated,
            suppressed_strategies=suppressed,
            position_size_multiplier=round(position_size, 2),
            reasoning=reasoning,
            individual_decisions=decisions,
            consensus=consensus,
        )


def _parse_analyst_response(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [line for line in lines if not line.strip().startswith("```")]
        cleaned = "\n".join(lines)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        logger.error("Failed to parse analyst response: %s", text[:200])
        return {
            "activated_strategies": [],
            "suppressed_strategies": [],
            "position_size_multiplier": 1.0,
            "reasoning": "Failed to parse response",
        }
