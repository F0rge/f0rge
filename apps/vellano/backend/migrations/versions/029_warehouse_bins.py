"""Warehouse bins (row × bay × level) and bin_stock rollup.

Revision ID: 029_warehouse_bins
Revises: 028_books_events
Create Date: 2026-09-01

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "029_warehouse_bins"
down_revision: Union[str, Sequence[str], None] = "028_books_events"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "location_bins",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("location_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("row_code", sa.String(length=8), nullable=False),
        sa.Column("bay", sa.Integer(), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("archived_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["location_id"],
            ["locations.id"],
            name="fk_location_bins_location_id_locations",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_location_bins"),
        sa.CheckConstraint("bay >= 1", name="ck_location_bins_bay"),
        sa.CheckConstraint("level >= 1", name="ck_location_bins_level"),
    )
    op.create_index("ix_location_bins_location_id", "location_bins", ["location_id"])
    op.create_index(
        "uq_location_bins_location_code_active",
        "location_bins",
        ["location_id", sa.text("lower(code)")],
        unique=True,
        postgresql_where=sa.text("NOT is_archived"),
    )
    op.create_index(
        "uq_location_bins_location_slot_active",
        "location_bins",
        ["location_id", "row_code", "bay", "level"],
        unique=True,
        postgresql_where=sa.text("NOT is_archived"),
    )
    op.create_index(
        "uq_location_bins_one_active_default",
        "location_bins",
        ["location_id"],
        unique=True,
        postgresql_where=sa.text("is_default AND NOT is_archived"),
    )

    op.create_table(
        "bin_stock",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sku_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bin_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("on_hand", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["sku_id"],
            ["skus.id"],
            name="fk_bin_stock_sku_id_skus",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["bin_id"],
            ["location_bins.id"],
            name="fk_bin_stock_bin_id_location_bins",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_bin_stock"),
        sa.UniqueConstraint("sku_id", "bin_id", name="uq_bin_stock_sku_bin"),
        sa.CheckConstraint("on_hand >= 0", name="ck_bin_stock_on_hand"),
    )
    op.create_index("ix_bin_stock_sku_id", "bin_stock", ["sku_id"])
    op.create_index("ix_bin_stock_bin_id", "bin_stock", ["bin_id"])

    op.execute(
        sa.text(
            """
            INSERT INTO location_bins (
                id, location_id, code, row_code, bay, level,
                is_default, is_archived, archived_at, created_at, updated_at
            )
            SELECT
                gen_random_uuid(),
                id,
                'FLOOR',
                'F',
                1,
                1,
                true,
                false,
                NULL,
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP
            FROM locations
            """
        )
    )
    op.execute(
        sa.text(
            """
            INSERT INTO bin_stock (id, sku_id, bin_id, on_hand, created_at, updated_at)
            SELECT
                gen_random_uuid(),
                ls.sku_id,
                b.id,
                ls.on_hand,
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP
            FROM location_stock ls
            INNER JOIN location_bins b
                ON b.location_id = ls.location_id
               AND b.code = 'FLOOR'
               AND NOT b.is_archived
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_bin_stock_bin_id", table_name="bin_stock")
    op.drop_index("ix_bin_stock_sku_id", table_name="bin_stock")
    op.drop_table("bin_stock")
    op.drop_index("uq_location_bins_one_active_default", table_name="location_bins")
    op.drop_index("uq_location_bins_location_slot_active", table_name="location_bins")
    op.drop_index("uq_location_bins_location_code_active", table_name="location_bins")
    op.drop_index("ix_location_bins_location_id", table_name="location_bins")
    op.drop_table("location_bins")
