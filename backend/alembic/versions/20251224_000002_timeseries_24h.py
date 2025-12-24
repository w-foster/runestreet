"""timeseries_24h cache

Revision ID: 20251224_000002
Revises: 20251224_000001
Create Date: 2025-12-24

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20251224_000002"
down_revision = "20251224_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "item_timeseries_24h_meta",
        sa.Column("item_id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("fetched_at", sa.BigInteger(), nullable=False),
    )

    op.create_table(
        "item_timeseries_24h",
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("bucket_ts", sa.BigInteger(), nullable=False),
        sa.Column("avg_high", sa.Integer(), nullable=True),
        sa.Column("high_vol", sa.Integer(), nullable=False),
        sa.Column("avg_low", sa.Integer(), nullable=True),
        sa.Column("low_vol", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("item_id", "bucket_ts"),
    )

    op.create_index(
        "ix_item_timeseries_24h_item_ts",
        "item_timeseries_24h",
        ["item_id", "bucket_ts"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_item_timeseries_24h_item_ts", table_name="item_timeseries_24h")
    op.drop_table("item_timeseries_24h")
    op.drop_table("item_timeseries_24h_meta")


