"""Decision pipeline — runs every 30 minutes to generate AI-driven trade signals."""

from __future__ import annotations

import json
import logging

import pandas as pd
import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession

from backend.brain.claude_client import ClaudeClient, RateLimitExceeded
from backend.brain.risk_manager import RiskManager
from backend.config import settings
from backend.database.models import Timeframe
from backend.database.repositories.backtests import BacktestRepository
from backend.database.repositories.candles import CandleRepository
from backend.database.repositories.decisions import DecisionRepository
from backend.database.repositories.performance import PerformanceRepository
from backend.database.repositories.signals import SignalRepository
from backend.strategies import ALL_STRATEGIES
from backend.strategies.base import SignalCandidate

logger = logging.getLogger(__name__)

SYMBOL = "XAU/USD"
CANDLE_LOAD_LIMIT = 200
COLD_START_THRESHOLD = 50  # Min resolved signals per strategy before using Claude ranking

DECISION_SYSTEM_PROMPT = """You are an expert gold (XAU/USD) trading analyst for an automated trading system.
You will receive:
1. Strategy performance rankings with composite scores
2. Current risk state
3. Market summary across 4 timeframes (15m, 1h, 4h, 1d)

Your job:
- Evaluate which strategies should be ACTIVATED or SUPPRESSED for the next 30-minute window
- Consider market conditions, volatility, and strategy suitability
- Be conservative when risk metrics are elevated

Respond with ONLY valid JSON in this exact format:
{
    "activated_strategies": ["strategy_name_1", "strategy_name_2"],
    "suppressed_strategies": ["strategy_name_3"],
    "position_size_multiplier": 1.0,
    "reasoning": "Brief explanation of your decision"
}

position_size_multiplier must be between 0.25 and 1.0 (reduce in uncertain conditions).
"""


def _compute_composite_score(perf) -> float:
    """Composite score: win_rate * avg_rr * (1 - max_drawdown)."""
    return perf.win_rate * perf.avg_rr * (1.0 - perf.max_drawdown)


def _summarise_candles(candles: dict[Timeframe, pd.DataFrame]) -> str:
    """Build a compact market summary from candle data."""
    lines = []
    for tf in [Timeframe.D1, Timeframe.H4, Timeframe.H1, Timeframe.M15]:
        df = candles.get(tf)
        if df is None or df.empty:
            continue
        last = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else last
        change_pct = ((last["close"] - prev["close"]) / prev["close"]) * 100
        high = df["high"].max()
        low = df["low"].min()
        lines.append(
            f"{tf.value}: close={last['close']:.2f}, change={change_pct:+.2f}%, "
            f"range=[{low:.2f}-{high:.2f}], bars={len(df)}"
        )
    return "\n".join(lines)


async def run_decision_pipeline(
    session: AsyncSession,
    redis: aioredis.Redis,
    claude_client: ClaudeClient,
) -> int:
    """Execute the full 30-minute decision pipeline. Returns number of signals created."""

    risk_mgr = RiskManager(session)
    candle_repo = CandleRepository(session)
    perf_repo = PerformanceRepository(session)
    signal_repo = SignalRepository(session)
    decision_repo = DecisionRepository(session)
    backtest_repo = BacktestRepository(session)

    # Step 1: Check risk state
    is_tradeable, risk_status = await risk_mgr.check_risk_state()
    if not is_tradeable:
        await decision_repo.log({
            "ranked_strategies": {},
            "risk_status": risk_status,
            "position_size_multiplier": 0.0,
            "notes": "Pipeline aborted: risk shutdown active",
        })
        logger.warning("Decision pipeline aborted: %s", risk_status)
        return 0

    # Step 2: Load candles for all 4 timeframes (200 bars each)
    candles: dict[Timeframe, pd.DataFrame] = {}
    for tf in Timeframe:
        rows = await candle_repo.get_range(symbol=SYMBOL, timeframe=tf, limit=CANDLE_LOAD_LIMIT)
        if not rows:
            continue
        data = [
            {
                "timestamp": r.timestamp,
                "open": r.open,
                "high": r.high,
                "low": r.low,
                "close": r.close,
                "volume": r.volume,
            }
            for r in sorted(rows, key=lambda c: c.timestamp)
        ]
        candles[tf] = pd.DataFrame(data)

    if not candles:
        logger.warning("Decision pipeline: no candle data available")
        return 0

    # Step 3: Load strategy performance metrics
    all_performance = await perf_repo.get_all()

    # Step 4: Rank strategies by composite score
    strategy_scores: dict[str, float] = {}
    perf_by_strategy: dict[str, list] = {}
    for perf in all_performance:
        score = _compute_composite_score(perf)
        # Keep best score across windows for each strategy
        if perf.strategy_name not in strategy_scores or score > strategy_scores[perf.strategy_name]:
            strategy_scores[perf.strategy_name] = score
        perf_by_strategy.setdefault(perf.strategy_name, []).append(perf)

    ranked = sorted(strategy_scores.items(), key=lambda x: x[1], reverse=True)
    ranked_dict = {name: round(score, 4) for name, score in ranked}

    # Cold start check: skip Claude ranking if insufficient data
    is_cold_start = True
    for strategy in ALL_STRATEGIES:
        perfs = perf_by_strategy.get(strategy.name, [])
        total = sum(p.total_signals for p in perfs)
        if total >= COLD_START_THRESHOLD:
            is_cold_start = False
            break

    if is_cold_start and not all_performance:
        is_cold_start = True

    # Step 5 & 6: Claude decision (or cold start defaults)
    activated_names: list[str] = []
    suppressed_names: list[str] = []
    position_size_multiplier = 1.0
    claude_reasoning = ""

    if is_cold_start:
        # Cold start: activate all strategies with equal weights
        activated_names = [s.name for s in ALL_STRATEGIES]
        claude_reasoning = "Cold start: insufficient performance data, activating all strategies with default params"
        logger.info("Cold start mode: activating all strategies")
    else:
        # Send to Claude for decision
        market_summary = _summarise_candles(candles)
        rankings_text = "\n".join(
            f"  {i+1}. {name}: score={score}" for i, (name, score) in enumerate(ranked)
        )

        user_prompt = f"""## Strategy Rankings (composite: win_rate * avg_rr * (1 - max_drawdown))
{rankings_text}

## Risk State
{risk_status}

## Market Summary (XAU/USD)
{market_summary}

## Available Strategies
{', '.join(s.name for s in ALL_STRATEGIES)}

Decide which strategies to activate for the next 30 minutes."""

        try:
            response_text = await claude_client.decide(DECISION_SYSTEM_PROMPT, user_prompt)
            decision = _parse_claude_response(response_text)
            activated_names = decision.get("activated_strategies", [])
            suppressed_names = decision.get("suppressed_strategies", [])
            position_size_multiplier = max(0.25, min(1.0, decision.get("position_size_multiplier", 1.0)))
            claude_reasoning = decision.get("reasoning", "")
        except RateLimitExceeded:
            logger.warning("Claude rate limit exceeded, using all strategies as fallback")
            activated_names = [s.name for s in ALL_STRATEGIES]
            claude_reasoning = "Rate limit exceeded — fallback to all strategies"
        except Exception:
            logger.exception("Claude decision call failed, using all strategies as fallback")
            activated_names = [s.name for s in ALL_STRATEGIES]
            claude_reasoning = "Claude call failed — fallback to all strategies"

    # Step 7: Run activated strategies
    activated_strategies = [s for s in ALL_STRATEGIES if s.name in activated_names]
    all_candidates: list[SignalCandidate] = []

    for strategy in activated_strategies:
        try:
            candidates = strategy.evaluate(candles)
            all_candidates.extend(candidates)
        except Exception:
            logger.exception("Strategy %s failed during evaluation", strategy.name)

    # Step 8: Filter by minimum confidence
    qualified = [c for c in all_candidates if c.confidence >= settings.min_signal_confidence]

    # Step 9: Persist signals
    created = 0
    for candidate in qualified:
        try:
            signal = await signal_repo.create({
                "strategy_name": candidate.strategy_name,
                "direction": candidate.direction,
                "entry_price": candidate.entry_price,
                "stop_loss": candidate.stop_loss,
                "take_profit": candidate.take_profit,
                "confidence_score": candidate.confidence,
                "reasoning": candidate.reasoning,
            })
            created += 1

            # Step 10: Publish to Redis
            await redis.publish(
                "signals:XAU/USD",
                json.dumps({
                    "type": "signal",
                    "data": {
                        "id": signal.id,
                        "strategy_name": signal.strategy_name,
                        "direction": signal.direction.value,
                        "entry_price": signal.entry_price,
                        "stop_loss": signal.stop_loss,
                        "take_profit": signal.take_profit,
                        "confidence_score": signal.confidence_score,
                        "status": signal.status.value,
                    },
                }),
            )
        except Exception:
            logger.exception("Failed to persist signal from %s", candidate.strategy_name)

    # Step 11: Log decision
    await decision_repo.log({
        "ranked_strategies": ranked_dict,
        "risk_status": risk_status,
        "position_size_multiplier": position_size_multiplier,
        "notes": (
            f"Activated: {activated_names}, Suppressed: {suppressed_names}, "
            f"Signals: {created}/{len(all_candidates)} qualified. "
            f"Claude: {claude_reasoning}"
        ),
    })

    logger.info(
        "Decision pipeline complete: %d signals created (%d candidates, %d qualified)",
        created,
        len(all_candidates),
        len(qualified),
    )
    return created


def _parse_claude_response(text: str) -> dict:
    """Parse Claude's JSON response, handling markdown code blocks."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        # Remove first and last lines (code block markers)
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        logger.error("Failed to parse Claude response as JSON: %s", text[:200])
        return {
            "activated_strategies": [],
            "suppressed_strategies": [],
            "position_size_multiplier": 1.0,
            "reasoning": "Failed to parse Claude response",
        }
