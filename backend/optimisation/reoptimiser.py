"""5.3 Parameter Reoptimisation — runs every 6 hours.

Per strategy: define parameter search space (ranges/choices).
Random search (NOT grid): 200 candidate param sets.
Mini-backtest each on 30-day window, score by Sharpe ratio.
Best candidate must pass walk-forward validation before promotion.
If none pass: retain existing params, log attempt.
Save winning params to optimised_params with is_active=true.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

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
from backend.optimisation.walk_forward import validate_strategy
from backend.strategies import ALL_STRATEGIES

logger = logging.getLogger(__name__)

NUM_CANDIDATES = 200
BACKTEST_WINDOW_DAYS = 30

# Parameter search spaces per strategy
# Each key maps to a dict of param_name -> (min, max) for floats/ints or list for choices
SEARCH_SPACES: dict[str, dict[str, Any]] = {
    "liquidity_sweep": {
        "eq_tolerance": (0.5, 3.0),
        "sl_atr_mult": (1.0, 2.5),
        "tp_atr_mult": (2.0, 5.0),
        "atr_period": (10, 20),
        "lookback": (30, 80),
        "min_touches": [2, 3, 4],
    },
    "trend_continuation": {
        "ema_fast": (20, 80),
        "ema_slow": (100, 300),
        "pullback_tolerance": (0.1, 0.6),
        "sl_atr_mult": (1.0, 2.5),
        "tp_atr_mult": (2.0, 5.0),
        "atr_period": (10, 20),
    },
    "breakout_expansion": {
        "squeeze_period": (10, 40),
        "breakout_atr_mult": (1.0, 2.5),
        "volume_threshold": (1.0, 2.0),
        "sl_atr_mult": (1.0, 2.5),
        "tp_atr_mult": (2.0, 5.0),
        "atr_period": (10, 20),
        "retest_tolerance": (0.2, 0.8),
    },
    "ema_momentum": {
        "ema_fast": (5, 15),
        "ema_mid": (15, 30),
        "ema_slow": (35, 70),
        "rsi_period": (10, 20),
        "rsi_long_threshold": (52.0, 60.0),
        "rsi_short_threshold": (40.0, 48.0),
        "sl_atr_mult": (1.0, 2.5),
        "tp_atr_mult": (2.0, 5.0),
        "atr_period": (10, 20),
        "ride_tolerance": (0.1, 0.5),
    },
}

# Integer parameters (sampled as int instead of float)
INT_PARAMS = {
    "ema_fast", "ema_mid", "ema_slow", "atr_period", "lookback",
    "squeeze_period", "rsi_period",
}


def _sample_params(strategy_name: str, rng: np.random.Generator) -> dict[str, Any]:
    """Sample a random parameter set from the search space."""
    space = SEARCH_SPACES.get(strategy_name, {})
    params: dict[str, Any] = {}

    for name, spec in space.items():
        if isinstance(spec, list):
            params[name] = spec[rng.integers(0, len(spec))]
        elif isinstance(spec, tuple) and len(spec) == 2:
            low, high = spec
            if name in INT_PARAMS:
                params[name] = int(rng.integers(int(low), int(high) + 1))
            else:
                params[name] = float(rng.uniform(low, high))
        else:
            params[name] = spec

    return params


async def _load_backtest_signals(
    session: AsyncSession, strategy_name: str
) -> list[Signal]:
    """Load resolved signals for the 30-day backtest window."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=BACKTEST_WINDOW_DAYS)
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


def _mini_backtest(signals: list[Signal], params: dict[str, Any]) -> float:
    """Score a parameter set against historical signals using Sharpe ratio.

    This is a simplified backtest that adjusts SL/TP multipliers on historical
    entries to estimate what the PnL would have been with different parameters.
    """
    if len(signals) < 2:
        return -999.0

    sl_mult = params.get("sl_atr_mult", 1.5)
    tp_mult = params.get("tp_atr_mult", 3.0)

    # Scale pips_result based on how the new TP/SL ratio compares to original (2:1 RR baseline)
    original_rr = 2.0
    new_rr = tp_mult / sl_mult if sl_mult > 0 else original_rr

    pnl = []
    for signal in signals:
        if signal.pips_result is None:
            continue
        original_pnl = signal.pips_result
        if original_pnl > 0:
            # Win: scale by new TP ratio
            scaled = original_pnl * (new_rr / original_rr)
        else:
            # Loss: scale by new SL ratio
            scaled = original_pnl * (sl_mult / 1.5)  # 1.5 is the default
        pnl.append(scaled)

    if len(pnl) < 2:
        return -999.0

    arr = np.array(pnl, dtype=np.float64)
    mean_ret = float(np.mean(arr))
    std_ret = float(np.std(arr))

    if std_ret <= 0:
        return 0.0

    # Annualised Sharpe
    return float(mean_ret / std_ret * np.sqrt(252))


async def _promote_params(
    session: AsyncSession, strategy_name: str, params: dict[str, Any], sharpe: float
) -> None:
    """Deactivate old params and save new winning params."""
    # Deactivate existing active params
    stmt = (
        update(OptimisedParams)
        .where(
            OptimisedParams.strategy_name == strategy_name,
            OptimisedParams.is_active.is_(True),
        )
        .values(is_active=False)
    )
    await session.execute(stmt)

    # Save new params
    now = datetime.now(timezone.utc)
    new_params = OptimisedParams(
        strategy_name=strategy_name,
        params={**params, "_sharpe": sharpe},
        is_active=True,
        validated_at=now,
    )
    session.add(new_params)

    logger.info(
        "Promoted new params for %s: sharpe=%.3f, params=%s",
        strategy_name, sharpe, params,
    )


async def _reoptimise_strategy(session: AsyncSession, strategy_name: str) -> bool:
    """Reoptimise a single strategy. Returns True if new params promoted."""
    signals = await _load_backtest_signals(session, strategy_name)

    if len(signals) < 5:
        logger.debug(
            "Reoptimise skip %s: only %d signals", strategy_name, len(signals)
        )
        return False

    rng = np.random.default_rng()

    # Random search: 200 candidates
    best_sharpe = -999.0
    best_params: dict[str, Any] | None = None

    for _ in range(NUM_CANDIDATES):
        params = _sample_params(strategy_name, rng)
        sharpe = _mini_backtest(signals, params)
        if sharpe > best_sharpe:
            best_sharpe = sharpe
            best_params = params

    if best_params is None or best_sharpe <= 0:
        logger.info(
            "Reoptimise %s: no candidate with positive Sharpe (best=%.3f)",
            strategy_name, best_sharpe,
        )
        # Store the failed attempt
        run = BacktestRun(
            run_type=BacktestRunType.REOPTIMISE,
            window_days=BACKTEST_WINDOW_DAYS,
            result=BacktestResult.FAIL,
            params_used=best_params,
            metrics={"strategy_name": strategy_name, "best_sharpe": best_sharpe},
        )
        session.add(run)
        return False

    # Walk-forward validation before promotion
    wf_result = await validate_strategy(session, strategy_name)

    run = BacktestRun(
        run_type=BacktestRunType.REOPTIMISE,
        window_days=BACKTEST_WINDOW_DAYS,
        result=BacktestResult.PASS if wf_result == BacktestResult.PASS else wf_result,
        params_used=best_params,
        metrics={
            "strategy_name": strategy_name,
            "best_sharpe": best_sharpe,
            "walk_forward_result": wf_result.value,
        },
    )
    session.add(run)

    if wf_result == BacktestResult.PASS:
        await _promote_params(session, strategy_name, best_params, best_sharpe)
        return True
    else:
        logger.info(
            "Reoptimise %s: best candidate (sharpe=%.3f) failed walk-forward (%s). Retaining existing params.",
            strategy_name, best_sharpe, wf_result.value,
        )
        return False


async def run_reoptimise(session: AsyncSession) -> dict[str, bool]:
    """Run parameter reoptimisation for all strategies.

    Returns dict mapping strategy_name -> whether new params were promoted.
    """
    results: dict[str, bool] = {}

    for strategy in ALL_STRATEGIES:
        promoted = await _reoptimise_strategy(session, strategy.name)
        results[strategy.name] = promoted

    await session.commit()

    promoted_count = sum(1 for v in results.values() if v)
    logger.info(
        "Reoptimisation complete: %d/%d strategies promoted new params",
        promoted_count, len(results),
    )
    return results
