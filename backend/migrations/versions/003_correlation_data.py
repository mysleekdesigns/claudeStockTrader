"""Add correlation_data table for cross-asset correlation tracking.

Revision ID: 003_correlation_data
Revises: 002_ab_test_runs
Create Date: 2026-03-24
"""

import sqlalchemy as sa

from alembic import op

revision = "003_correlation_data"
down_revision = "002_ab_test_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "correlation_data",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("asset", sa.String(20), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_correlation_data_asset_ts",
        "correlation_data",
        ["asset", "timestamp"],
    )


def downgrade() -> None:
    op.drop_index("ix_correlation_data_asset_ts", table_name="correlation_data")
    op.drop_table("correlation_data")
