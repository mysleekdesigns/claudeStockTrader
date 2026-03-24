"""Add ab_test_runs table for A/B testing framework.

Revision ID: 002_ab_test_runs
Revises: 001_initial
Create Date: 2026-03-24
"""

import sqlalchemy as sa

from alembic import op

revision = "002_ab_test_runs"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ab_test_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("variant_name", sa.String(100), nullable=False),
        sa.Column("decision_cycle_id", sa.Integer(), nullable=False),
        sa.Column("signals_created", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("signals_won", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("signals_lost", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("win_rate", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ab_test_variant_cycle",
        "ab_test_runs",
        ["variant_name", "decision_cycle_id"],
    )


def downgrade() -> None:
    op.drop_table("ab_test_runs")
