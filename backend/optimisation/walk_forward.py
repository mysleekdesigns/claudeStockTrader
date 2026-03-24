"""5.2 Walk-Forward Validation.

80/20 train/test split on 60-day signal history (non-overlapping).
Compute metrics on both sets (win_rate, Sharpe, max_drawdown).
Flag overfitting if test win_rate drops > 20 percentage points vs train.
If overfit: deactivate current params for that strategy.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import numpy as np
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import (
    BacktestResult,
    BacktestRun,
    BacktestRunType,
    OptimisedParams,
    Signal,
    SignalStatus,
)

logger = logging.getLogger(__name__)

WINDOW_DAYS = 60
TRAIN_RATIO = 0.80
OVERFIT_THRESHOLD_PP = 20.0  # percentage points


def _compute_metrics(pnl: np.ndarray) -> dict:
    """Compute trading metrics from a PnL array."""
    if len(pnl) == 0:
        return {"win_rate": 0.0, "sharpe": 0.0, "max_drawdown": 0.0, "n_signals": 0}

    win_rate = float(np.sum(pnl > 0) / len(pnl))

    # Sharpe ratio (annualised, assume ~252 trading days, 1 signal per day average)
    mean_ret = float(np.mean(pnl))
    std_ret = float(np.std(pnl))
    sharpe = (mean_ret / std_ret * np.sqrt(252)) if std_ret > 0 else 0.0

    # Max drawdown
    cumulative = np.cumsum(pnl)
    running_max = np.maximum.accumulate(cumulative)
    drawdowns = running_max - cumulative
    max_drawdown = float(drawdowns.max()) if len(drawdowns) > 0 else 0.0

    return {
        "win_rate": win_rate,
        "sharpe": sharpe,
        "max_drawdown": max_drawdown,
        "n_signals": len(pnl),
    }


async def _load_signals_for_window(
    session: AsyncSession, strategy_name: str
) -> list[Signal]:
    """Load resolved signals for the 60-day window, ordered by resolved_at."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=WINDOW_DAYS)
    query = (
        select(Signal)
        .where(
            Signal.strategy_name == strategy_name,
            Signal.status.in_([SignalStatus.WON, SignalStatus.LOST]),
            Signal.resolved_at >= cutoff,
            Signal.pips_result.isnot(None),
        )
        .order_by(Signal.resolved_at.asc())
    )
    result = await session.execute(query)
    return list(result.scalars().all())


async def _deactivate_params(session: AsyncSession, strategy_name: str) -> None:
    """Deactivate current optimised params for a strategy flagged as overfit."""
    stmt = (
        update(OptimisedParams)
        .where(
            OptimisedParams.strategy_name == strategy_name,
            OptimisedParams.is_active.is_(True),
        )
        .values(is_active=False)
    )
    await session.execute(stmt)
    logger.warning("Deactivated params for overfit strategy: %s", strategy_name)


async def validate_strategy(
    session: AsyncSession, strategy_name: str
) -> BacktestResult:
    """Run walk-forward validation for a single strategy.

    Returns BacktestResult.PASS, FAIL (insufficient data), or OVERFIT.
    """
    signals = await _load_signals_for_window(session, strategy_name)
    pnl_array = np.array(
        [s.pips_result for s in signals if s.pips_result is not None],
        dtype=np.float64,
    )

    if len(pnl_array) < 5:
        logger.debug(
            "Walk-forward skip %s: only %d signals", strategy_name, len(pnl_array)
        )
        return BacktestResult.FAIL

    # 80/20 non-overlapping split
    split_idx = int(len(pnl_array) * TRAIN_RATIO)
    train_pnl = pnl_array[:split_idx]
    test_pnl = pnl_array[split_idx:]

    if len(test_pnl) == 0:
        return BacktestResult.FAIL

    train_metrics = _compute_metrics(train_pnl)
    test_metrics = _compute_metrics(test_pnl)

    # Overfitting check: test win_rate drops > 20pp vs train
    wr_drop_pp = (train_metrics["win_rate"] - test_metrics["win_rate"]) * 100.0
    is_overfit = wr_drop_pp > OVERFIT_THRESHOLD_PP

    result = BacktestResult.OVERFIT if is_overfit else BacktestResult.PASS

    now = datetime.now(timezone.utc)
    train_start = now - timedelta(days=WINDOW_DAYS)
    test_start = train_start + timedelta(days=int(WINDOW_DAYS * TRAIN_RATIO))

    run = BacktestRun(
        run_type=BacktestRunType.WALK_FORWARD,
        window_days=WINDOW_DAYS,
        train_start=train_start,
        test_start=test_start,
        test_end=now,
        result=result,
        metrics={
            "strategy_name": strategy_name,
            "train": train_metrics,
            "test": test_metrics,
            "win_rate_drop_pp": float(wr_drop_pp),
            "is_overfit": is_overfit,
        },
    )
    session.add(run)

    if is_overfit:
        await _deactivate_params(session, strategy_name)
        logger.warning(
            "OVERFIT detected for %s: train WR=%.1f%%, test WR=%.1f%% (drop=%.1fpp)",
            strategy_name,
            train_metrics["win_rate"] * 100,
            test_metrics["win_rate"] * 100,
            wr_drop_pp,
        )
    else:
        logger.info(
            "Walk-forward PASS for %s: train WR=%.1f%%, test WR=%.1f%%",
            strategy_name,
            train_metrics["win_rate"] * 100,
            test_metrics["win_rate"] * 100,
        )

    return result


async def run_walk_forward(session: AsyncSession) -> dict[str, BacktestResult]:
    """Run walk-forward validation for all strategies.

    Returns dict mapping strategy_name -> BacktestResult.
    """
    from backend.strategies import ALL_STRATEGIES

    results: dict[str, BacktestResult] = {}

    for strategy in ALL_STRATEGIES:
        result = await validate_strategy(session, strategy.name)
        results[strategy.name] = result

    await session.commit()

    logger.info("Walk-forward complete: %s", {k: v.value for k, v in results.items()})
    return results
