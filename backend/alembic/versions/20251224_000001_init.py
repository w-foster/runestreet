"""init

Revision ID: 20251224_000001
Revises:
Create Date: 2025-12-24

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20251224_000001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "item_mapping",
        sa.Column("item_id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("limit", sa.Integer(), nullable=True),
        sa.Column("members", sa.Boolean(), nullable=True),
        sa.Column("value", sa.Integer(), nullable=True),
        sa.Column("lowalch", sa.Integer(), nullable=True),
        sa.Column("highalch", sa.Integer(), nullable=True),
        sa.Column("icon", sa.Text(), nullable=True),
        sa.Column("examine", sa.Text(), nullable=True),
        sa.Column("mapping_fetched_at", sa.BigInteger(), nullable=False),
    )

    op.create_table(
        "bucket_5m",
        sa.Column("bucket_ts", sa.BigInteger(), primary_key=True, nullable=False),
        sa.Column("ingested_at", sa.BigInteger(), nullable=False),
    )

    op.create_table(
        "item_bucket_5m",
        sa.Column("bucket_ts", sa.BigInteger(), nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("avg_high", sa.Integer(), nullable=True),
        sa.Column("high_vol", sa.Integer(), nullable=False),
        sa.Column("avg_low", sa.Integer(), nullable=True),
        sa.Column("low_vol", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("bucket_ts", "item_id"),
    )

    op.create_index(
        "ix_item_bucket_5m_item_ts",
        "item_bucket_5m",
        ["item_id", "bucket_ts"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_item_bucket_5m_item_ts", table_name="item_bucket_5m")
    op.drop_table("item_bucket_5m")
    op.drop_table("bucket_5m")
    op.drop_table("item_mapping")


