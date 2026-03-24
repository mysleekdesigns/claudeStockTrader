import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


# --- Enums ---


class Timeframe(str, enum.Enum):
    M15 = "15m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"


class SignalDirection(str, enum.Enum):
    LONG = "long"
    SHORT = "short"


class SignalStatus(str, enum.Enum):
    PENDING = "pending"
    ACTIVE = "active"
    WON = "won"
    LOST = "lost"
    EXPIRED = "expired"


class BacktestRunType(str, enum.Enum):
    MONTE_CARLO = "monte_carlo"
    WALK_FORWARD = "walk_forward"
    REOPTIMISE = "reoptimise"


class BacktestResult(str, enum.Enum):
    PASS = "pass"
    FAIL = "fail"
    OVERFIT = "overfit"


# --- Models ---


class Candle(Base):
    __tablename__ = "candles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    timeframe: Mapped[Timeframe] = mapped_column(Enum(Timeframe, values_callable=lambda e: [m.value for m in e]), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    open: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    __table_args__ = (
        UniqueConstraint("symbol", "timeframe", "timestamp", name="uq_candle_symbol_tf_ts"),
        Index("ix_candle_symbol_tf_ts_desc", "symbol", "timeframe", timestamp.desc()),
    )


class Signal(Base):
    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    strategy_name: Mapped[str] = mapped_column(String(100), nullable=False)
    direction: Mapped[SignalDirection] = mapped_column(Enum(SignalDirection, values_callable=lambda e: [m.value for m in e]), nullable=False)
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    stop_loss: Mapped[float] = mapped_column(Float, nullable=False)
    take_profit: Mapped[float] = mapped_column(Float, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[SignalStatus] = mapped_column(Enum(SignalStatus, values_callable=lambda e: [m.value for m in e]), nullable=False, default=SignalStatus.PENDING)
    pips_result: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (Index("ix_signal_status_created", "status", "created_at"),)


class StrategyPerformance(Base):
    __tablename__ = "strategy_performance"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    strategy_name: Mapped[str] = mapped_column(String(100), nullable=False)
    window_days: Mapped[int] = mapped_column(Integer, nullable=False)
    win_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    avg_rr: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_signals: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sharpe_ratio: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    max_drawdown: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class BacktestRun(Base):
    __tablename__ = "backtest_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_type: Mapped[BacktestRunType] = mapped_column(Enum(BacktestRunType, values_callable=lambda e: [m.value for m in e]), nullable=False)
    window_days: Mapped[int] = mapped_column(Integer, nullable=False)
    train_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    test_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    test_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    result: Mapped[BacktestResult] = mapped_column(Enum(BacktestResult, values_callable=lambda e: [m.value for m in e]), nullable=False)
    params_used: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    metrics: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class OptimisedParams(Base):
    __tablename__ = "optimised_params"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    strategy_name: Mapped[str] = mapped_column(String(100), nullable=False)
    params: Mapped[dict] = mapped_column(JSONB, nullable=False)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RiskState(Base):
    __tablename__ = "risk_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    daily_loss_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    consecutive_stops: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_shutdown: Mapped[bool] = mapped_column(nullable=False, default=False)
    shutdown_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CorrelationData(Base):
    __tablename__ = "correlation_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    asset: Mapped[str] = mapped_column(String(20), nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_correlation_data_asset_ts", "asset", "timestamp"),
    )


class DecisionLog(Base):
    __tablename__ = "decision_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ranked_strategies: Mapped[dict] = mapped_column(JSONB, nullable=False)
    risk_status: Mapped[str] = mapped_column(String(50), nullable=False)
    position_size_multiplier: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (Index("ix_decision_log_created", "created_at"),)


class ABTestRun(Base):
    __tablename__ = "ab_test_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    variant_name: Mapped[str] = mapped_column(String(100), nullable=False)
    decision_cycle_id: Mapped[int] = mapped_column(Integer, nullable=False)
    signals_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    signals_won: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    signals_lost: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    win_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (Index("ix_ab_test_variant_cycle", "variant_name", "decision_cycle_id"),)
