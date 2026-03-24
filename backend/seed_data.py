"""Seed the database with realistic XAU/USD sample data."""
import asyncio
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from database.models import (
    Base, Candle, Signal, StrategyPerformance, DecisionLog, RiskState,
    BacktestRun, OptimisedParams,
    Timeframe, SignalDirection, SignalStatus, BacktestRunType, BacktestResult,
)
from config import settings

engine = create_async_engine(settings.database_url)
Session = async_sessionmaker(engine, expire_on_commit=False)

STRATEGIES = ["liquidity_sweep", "trend_continuation", "breakout_expansion", "ema_momentum"]
NOW = datetime.now(timezone.utc)


def generate_candles(timeframe: Timeframe, count: int, interval_minutes: int) -> list[Candle]:
    """Generate realistic XAU/USD candle data with random walk."""
    candles = []
    price = 2330.0 + random.uniform(-50, 50)
    start = NOW - timedelta(minutes=interval_minutes * count)

    for i in range(count):
        ts = start + timedelta(minutes=interval_minutes * i)
        volatility = random.uniform(0.5, 3.0)
        open_price = price
        close_price = open_price + random.uniform(-volatility, volatility)
        high_price = max(open_price, close_price) + random.uniform(0.1, volatility)
        low_price = min(open_price, close_price) - random.uniform(0.1, volatility)
        volume = random.uniform(100, 5000)

        candles.append(Candle(
            symbol="XAU/USD",
            timeframe=timeframe,
            timestamp=ts,
            open=round(open_price, 2),
            high=round(high_price, 2),
            low=round(low_price, 2),
            close=round(close_price, 2),
            volume=round(volume, 2),
        ))
        price = close_price + random.uniform(-0.5, 0.5)

    return candles


def generate_signals(candles_1h: list[Candle]) -> list[Signal]:
    """Generate sample signals tied to candle prices."""
    signals = []
    statuses = [SignalStatus.WON, SignalStatus.LOST, SignalStatus.WON, SignalStatus.WON,
                SignalStatus.EXPIRED, SignalStatus.WON, SignalStatus.LOST]
    reasonings = [
        "Strong liquidity sweep detected above equal highs with bullish reversal confirmation on 15m. Volume expansion supports the move.",
        "Price pulled back to 50 EMA on 1h chart within established 4h uptrend. Bullish engulfing candle confirms entry.",
        "Daily range compression detected (ATR squeeze). Breakout above resistance with volume confirmation on 4h.",
        "8/21/50 EMA fan-out on 1h with RSI above 55 confirming momentum. Price riding the 8 EMA.",
        "Equal lows swept on 1h chart with bearish rejection wick. 15m shows bearish engulfing confirmation.",
        "Downtrend continuation after pullback to 50 EMA rejected. Clean bearish structure on 4h.",
        "Consolidation breakout to the downside with expanding volume. Retest of broken support as resistance.",
    ]

    for i in range(30):
        candle = candles_1h[min(i * 8 + random.randint(0, 5), len(candles_1h) - 1)]
        strategy = random.choice(STRATEGIES)
        direction = random.choice([SignalDirection.LONG, SignalDirection.SHORT])
        entry = candle.close
        atr = random.uniform(8, 25)

        if direction == SignalDirection.LONG:
            sl = round(entry - atr * 1.5, 2)
            tp = round(entry + atr * 3.0, 2)
        else:
            sl = round(entry + atr * 1.5, 2)
            tp = round(entry - atr * 3.0, 2)

        status = statuses[i % len(statuses)]
        pips = None
        resolved_at = None
        if status == SignalStatus.WON:
            pips = round(abs(tp - entry), 2)
            resolved_at = candle.timestamp + timedelta(hours=random.randint(2, 24))
        elif status == SignalStatus.LOST:
            pips = -round(abs(sl - entry), 2)
            resolved_at = candle.timestamp + timedelta(hours=random.randint(1, 12))

        # Make last 3 signals active/pending
        if i >= 28:
            status = SignalStatus.PENDING if i == 29 else SignalStatus.ACTIVE
            pips = None
            resolved_at = None

        signals.append(Signal(
            strategy_name=strategy,
            direction=direction,
            entry_price=round(entry, 2),
            stop_loss=sl,
            take_profit=tp,
            confidence_score=round(random.uniform(0.62, 0.95), 2),
            reasoning=reasonings[i % len(reasonings)],
            status=status,
            pips_result=pips,
            created_at=candle.timestamp,
            resolved_at=resolved_at,
        ))

    return signals


def generate_strategy_performance() -> list[StrategyPerformance]:
    """Generate performance metrics for each strategy."""
    rows = []
    perf_data = {
        "liquidity_sweep": {"win_rate": 0.58, "avg_rr": 2.1, "sharpe": 1.45, "dd": 0.08},
        "trend_continuation": {"win_rate": 0.62, "avg_rr": 1.8, "sharpe": 1.72, "dd": 0.06},
        "breakout_expansion": {"win_rate": 0.52, "avg_rr": 2.5, "sharpe": 1.15, "dd": 0.12},
        "ema_momentum": {"win_rate": 0.55, "avg_rr": 1.6, "sharpe": 1.30, "dd": 0.09},
    }
    for strategy, data in perf_data.items():
        for window in [7, 30, 90]:
            noise = random.uniform(-0.03, 0.03)
            rows.append(StrategyPerformance(
                strategy_name=strategy,
                window_days=window,
                win_rate=round(data["win_rate"] + noise, 3),
                avg_rr=round(data["avg_rr"] + random.uniform(-0.2, 0.2), 2),
                total_signals=random.randint(15, 120),
                sharpe_ratio=round(data["sharpe"] + random.uniform(-0.2, 0.2), 2),
                max_drawdown=round(data["dd"] + random.uniform(-0.02, 0.02), 3),
            ))
    return rows


def generate_decisions() -> list[DecisionLog]:
    """Generate sample decision log entries."""
    decisions = []
    for i in range(12):
        ts = NOW - timedelta(minutes=30 * (12 - i))
        active = random.sample(STRATEGIES, k=random.randint(2, 4))
        decisions.append(DecisionLog(
            ranked_strategies=[
                {"name": s, "score": round(random.uniform(0.5, 1.5), 3), "rank": j + 1}
                for j, s in enumerate(STRATEGIES)
            ],
            risk_status="normal" if i < 10 else "elevated",
            position_size_multiplier=round(random.uniform(0.7, 1.0), 2),
            notes=f"Pipeline cycle {i+1}: activated {', '.join(active)}. "
                  f"{'Market showing strong trend.' if i % 2 == 0 else 'Consolidation phase, reduced exposure.'}",
            created_at=ts,
        ))
    return decisions


def generate_backtest_runs() -> list[BacktestRun]:
    rows = []
    for strategy in STRATEGIES:
        for window in [7, 14, 30, 60]:
            rows.append(BacktestRun(
                run_type=BacktestRunType.MONTE_CARLO,
                window_days=window,
                train_start=NOW - timedelta(days=window),
                test_start=NOW - timedelta(days=int(window * 0.2)),
                test_end=NOW,
                result=random.choice([BacktestResult.PASS, BacktestResult.PASS, BacktestResult.FAIL]),
                params_used={"strategy": strategy},
                metrics={
                    "mean_drawdown": round(random.uniform(0.03, 0.12), 3),
                    "p95_drawdown": round(random.uniform(0.08, 0.20), 3),
                    "win_rate": round(random.uniform(0.48, 0.65), 3),
                    "reshuffles": 1000,
                },
                created_at=NOW - timedelta(hours=random.randint(1, 48)),
            ))
    return rows


def generate_optimised_params() -> list[OptimisedParams]:
    param_defs = {
        "liquidity_sweep": {"eq_tolerance": 0.5, "sl_atr_mult": 1.5, "tp_atr_mult": 3.0, "atr_period": 14},
        "trend_continuation": {"ema_fast": 50, "ema_slow": 200, "pullback_tolerance": 0.3, "sl_atr_mult": 1.5},
        "breakout_expansion": {"squeeze_period": 20, "breakout_atr_mult": 1.2, "volume_threshold": 1.5},
        "ema_momentum": {"ema_fast": 8, "ema_mid": 21, "ema_slow": 50, "rsi_period": 14, "rsi_threshold": 55},
    }
    return [
        OptimisedParams(
            strategy_name=name,
            params=params,
            is_active=True,
            validated_at=NOW - timedelta(hours=random.randint(1, 24)),
        )
        for name, params in param_defs.items()
    ]


async def seed():
    async with Session() as session:
        # Generate candles for all timeframes
        print("Generating candles...")
        all_candles = []
        configs = [
            (Timeframe.M15, 500, 15),
            (Timeframe.H1, 300, 60),
            (Timeframe.H4, 200, 240),
            (Timeframe.D1, 90, 1440),
        ]
        for tf, count, interval in configs:
            candles = generate_candles(tf, count, interval)
            all_candles.extend(candles)
            print(f"  {tf.value}: {count} candles")

        session.add_all(all_candles)

        # Get 1h candles for signal generation
        candles_1h = [c for c in all_candles if c.timeframe == Timeframe.H1]

        print("Generating signals...")
        signals = generate_signals(candles_1h)
        session.add_all(signals)
        print(f"  {len(signals)} signals")

        print("Generating strategy performance...")
        perf = generate_strategy_performance()
        session.add_all(perf)

        print("Generating decision log...")
        decisions = generate_decisions()
        session.add_all(decisions)

        print("Generating backtest runs...")
        backtests = generate_backtest_runs()
        session.add_all(backtests)

        print("Generating optimised params...")
        params = generate_optimised_params()
        session.add_all(params)

        print("Generating risk state...")
        risk = RiskState(
            date=NOW,
            daily_loss_pct=0.004,
            consecutive_stops=2,
            is_shutdown=False,
        )
        session.add(risk)

        await session.commit()
        print("\nDone! Database seeded with sample data.")
        print(f"  Candles: {len(all_candles)}")
        print(f"  Signals: {len(signals)}")
        print(f"  Strategy perf: {len(perf)}")
        print(f"  Decisions: {len(decisions)}")
        print(f"  Backtests: {len(backtests)}")
        print(f"  Params: {len(params)}")


if __name__ == "__main__":
    asyncio.run(seed())
