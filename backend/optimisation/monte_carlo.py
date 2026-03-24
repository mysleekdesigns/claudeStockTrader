"""5.1 Monte Carlo Simulation — runs every 4 hours.

For each strategy x each window (7, 14, 30, 60 days):
  - Load resolved signals, extract PnL array
  - Reshuffle 1,000 times (minimum)
  - Compute: mean drawdown, P95 drawdown, win rate distribution
  - Store results to backtest_runs table
  - Claude Haiku summarises findings across all strategies
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import (
    BacktestResult,
    BacktestRun,
    BacktestRunType,
    Signal,
    SignalStatus,
)
from backend.strategies import ALL_STRATEGIES

logger = logging.getLogger(__name__)

WINDOWS = [7, 14, 30, 60]
NUM_RESHUFFLES = 1_000


def _compute_drawdown_series(pnl: np.ndarray) -> np.ndarray:
    """Compute drawdown series from a PnL array."""
    cumulative = np.cumsum(pnl)
    running_max = np.maximum.accumulate(cumulative)
    drawdowns = running_max - cumulative
    return drawdowns


def _monte_carlo_sim(pnl: np.ndarray, n_reshuffles: int) -> dict:
    """Run Monte Carlo simulation on a PnL array.

    Returns dict with mean_drawdown, p95_drawdown, win_rate_mean, win_rate_std.
    """
    rng = np.random.default_rng()
    max_drawdowns = np.empty(n_reshuffles)
    win_rates = np.empty(n_reshuffles)

    for i in range(n_reshuffles):
        shuffled = rng.permutation(pnl)
        dd = _compute_drawdown_series(shuffled)
        max_drawdowns[i] = float(dd.max()) if len(dd) > 0 else 0.0
        win_rates[i] = float(np.sum(shuffled > 0) / len(shuffled)) if len(shuffled) > 0 else 0.0

    return {
        "mean_drawdown": float(np.mean(max_drawdowns)),
        "p95_drawdown": float(np.percentile(max_drawdowns, 95)),
        "win_rate_mean": float(np.mean(win_rates)),
        "win_rate_std": float(np.std(win_rates)),
        "max_drawdown_std": float(np.std(max_drawdowns)),
    }


async def _load_resolved_pnl(
    session: AsyncSession, strategy_name: str, window_days: int
) -> np.ndarray:
    """Load resolved signal PnL for a strategy within a time window."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    query = (
        select(Signal.pips_result)
        .where(
            Signal.strategy_name == strategy_name,
            Signal.status.in_([SignalStatus.WON, SignalStatus.LOST]),
            Signal.resolved_at >= cutoff,
            Signal.pips_result.isnot(None),
        )
        .order_by(Signal.resolved_at.asc())
    )
    result = await session.execute(query)
    values = [row[0] for row in result.all()]
    return np.array(values, dtype=np.float64)


async def _run_strategy_window(
    session: AsyncSession, strategy_name: str, window_days: int
) -> dict | None:
    """Run Monte Carlo for a single strategy x window combination."""
    pnl = await _load_resolved_pnl(session, strategy_name, window_days)

    if len(pnl) < 2:
        logger.debug(
            "Skipping MC for %s/%dd — only %d resolved signals",
            strategy_name, window_days, len(pnl),
        )
        return None

    mc_results = _monte_carlo_sim(pnl, NUM_RESHUFFLES)

    now = datetime.now(timezone.utc)
    metrics = {
        "strategy_name": strategy_name,
        "n_signals": len(pnl),
        "n_reshuffles": NUM_RESHUFFLES,
        "original_win_rate": float(np.sum(pnl > 0) / len(pnl)),
        "original_max_drawdown": float(_compute_drawdown_series(pnl).max()),
        **mc_results,
    }

    result = BacktestResult.PASS
    # Flag if P95 drawdown is significantly worse than mean
    if mc_results["p95_drawdown"] > mc_results["mean_drawdown"] * 2.0:
        result = BacktestResult.FAIL

    run = BacktestRun(
        run_type=BacktestRunType.MONTE_CARLO,
        window_days=window_days,
        train_start=now - timedelta(days=window_days),
        test_end=now,
        result=result,
        metrics=metrics,
    )
    session.add(run)

    return metrics


async def _summarise_with_claude(
    session: AsyncSession, all_results: list[dict]
) -> str | None:
    """Use Claude Haiku to summarise MC findings across all strategies."""
    if not all_results:
        return None

    try:
        import redis.asyncio as aioredis

        from backend.brain.claude_client import ClaudeClient
        from backend.config import settings

        redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
        try:
            claude = ClaudeClient(redis_client)

            system_prompt = (
                "You are a quantitative trading analyst. Summarise the Monte Carlo "
                "simulation results across strategies. Highlight risk concentration, "
                "strategies with unstable win rates, and any drawdown concerns. "
                "Be concise (max 300 words)."
            )

            results_text = "\n".join(
                f"- {r['strategy_name']} ({r.get('n_signals', 0)} signals, window not specified): "
                f"WR={r['original_win_rate']:.2%}, MC WR={r['win_rate_mean']:.2%} +/- {r['win_rate_std']:.2%}, "
                f"Mean DD={r['mean_drawdown']:.2f}, P95 DD={r['p95_drawdown']:.2f}"
                for r in all_results
            )

            summary = await claude.analyze(system_prompt, results_text)
            logger.info("Claude MC summary: %s", summary[:200])
            return summary
        finally:
            await redis_client.aclose()
    except Exception:
        logger.exception("Failed to get Claude MC summary")
        return None


async def run_monte_carlo(session: AsyncSession) -> int:
    """Run Monte Carlo simulation for all strategies across all windows.

    Returns the number of backtest runs stored.
    """
    all_results: list[dict] = []
    runs_stored = 0

    for strategy in ALL_STRATEGIES:
        for window in WINDOWS:
            result = await _run_strategy_window(session, strategy.name, window)
            if result is not None:
                all_results.append(result)
                runs_stored += 1

    await session.commit()

    # Claude Haiku summary (best-effort, does not block)
    await _summarise_with_claude(session, all_results)

    logger.info("Monte Carlo complete: %d runs stored", runs_stored)
    return runs_stored
