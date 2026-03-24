"""Initial schema — all 7 tables.

Revision ID: 001_initial
Revises:
Create Date: 2026-03-24
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None

# Enum types
timeframe_enum = postgresql.ENUM("15m", "1h", "4h", "1d", name="timeframe", create_type=False)
signal_direction_enum = postgresql.ENUM("long", "short", name="signaldirection", create_type=False)
signal_status_enum = postgresql.ENUM(
    "pending", "active", "won", "lost", "expired", name="signalstatus", create_type=False
)
backtest_run_type_enum = postgresql.ENUM(
    "monte_carlo", "walk_forward", "reoptimise", name="backtestruntype", create_type=False
)
backtest_result_enum = postgresql.ENUM(
    "pass", "fail", "overfit", name="backtestresult", create_type=False
)


def upgrade() -> None:
    # Create enum types
    timeframe_enum.create(op.get_bind(), checkfirst=True)
    signal_direction_enum.create(op.get_bind(), checkfirst=True)
    signal_status_enum.create(op.get_bind(), checkfirst=True)
    backtest_run_type_enum.create(op.get_bind(), checkfirst=True)
    backtest_result_enum.create(op.get_bind(), checkfirst=True)

    # candles
    op.create_table(
        "candles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("timeframe", timeframe_enum, nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open", sa.Float(), nullable=False),
        sa.Column("high", sa.Float(), nullable=False),
        sa.Column("low", sa.Float(), nullable=False),
        sa.Column("close", sa.Float(), nullable=False),
        sa.Column("volume", sa.Float(), nullable=False, server_default="0.0"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("symbol", "timeframe", "timestamp", name="uq_candle_symbol_tf_ts"),
    )
    op.create_index(
        "ix_candle_symbol_tf_ts_desc",
        "candles",
        ["symbol", "timeframe", sa.text("timestamp DESC")],
    )

    # signals
    op.create_table(
        "signals",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("strategy_name", sa.String(100), nullable=False),
        sa.Column("direction", signal_direction_enum, nullable=False),
        sa.Column("entry_price", sa.Float(), nullable=False),
        sa.Column("stop_loss", sa.Float(), nullable=False),
        sa.Column("take_profit", sa.Float(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("reasoning", sa.Text(), nullable=True),
        sa.Column("status", signal_status_enum, nullable=False, server_default="pending"),
        sa.Column("pips_result", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_signal_status_created", "signals", ["status", "created_at"])

    # strategy_performance
    op.create_table(
        "strategy_performance",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("strategy_name", sa.String(100), nullable=False),
        sa.Column("window_days", sa.Integer(), nullable=False),
        sa.Column("win_rate", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("avg_rr", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("total_signals", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sharpe_ratio", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("max_drawdown", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # backtest_runs
    op.create_table(
        "backtest_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_type", backtest_run_type_enum, nullable=False),
        sa.Column("window_days", sa.Integer(), nullable=False),
        sa.Column("train_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("test_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("test_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result", backtest_result_enum, nullable=False),
        sa.Column("params_used", postgresql.JSONB(), nullable=True),
        sa.Column("metrics", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # optimised_params
    op.create_table(
        "optimised_params",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("strategy_name", sa.String(100), nullable=False),
        sa.Column("params", postgresql.JSONB(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # risk_state
    op.create_table(
        "risk_state",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("daily_loss_pct", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("consecutive_stops", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_shutdown", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("shutdown_until", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # decision_log
    op.create_table(
        "decision_log",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ranked_strategies", postgresql.JSONB(), nullable=False),
        sa.Column("risk_status", sa.String(50), nullable=False),
        sa.Column("position_size_multiplier", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_decision_log_created", "decision_log", ["created_at"])


def downgrade() -> None:
    op.drop_table("decision_log")
    op.drop_table("risk_state")
    op.drop_table("optimised_params")
    op.drop_table("backtest_runs")
    op.drop_table("strategy_performance")
    op.drop_table("signals")
    op.drop_table("candles")

    backtest_result_enum.drop(op.get_bind(), checkfirst=True)
    backtest_run_type_enum.drop(op.get_bind(), checkfirst=True)
    signal_status_enum.drop(op.get_bind(), checkfirst=True)
    signal_direction_enum.drop(op.get_bind(), checkfirst=True)
    timeframe_enum.drop(op.get_bind(), checkfirst=True)
