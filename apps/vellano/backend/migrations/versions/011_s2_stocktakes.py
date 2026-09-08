"""stocktakes and stocktake_lines.

Revision ID: 011_s2_stocktakes
Revises: 010_s10_cockpit
Create Date: 2026-09-01

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "011_s2_stocktakes"
down_revision: Union[str, Sequence[str], None] = "010_s10_cockpit"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "stocktakes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("location_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["location_id"],
            ["locations.id"],
            name="fk_stocktakes_location_id_locations",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name="fk_stocktakes_created_by_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_stocktakes"),
        sa.CheckConstraint(
            "status IN ('in_progress', 'completed', 'cancelled')",
            name="ck_stocktakes_status",
        ),
    )
    op.create_index("ix_stocktakes_location_id", "stocktakes", ["location_id"])
    op.create_index("ix_stocktakes_created_by_user_id", "stocktakes", ["created_by_user_id"])
    op.create_index(
        "uq_stocktakes_location_in_progress",
        "stocktakes",
        ["location_id"],
        unique=True,
        postgresql_where=sa.text("status = 'in_progress'"),
    )

    op.create_table(
        "stocktake_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("stocktake_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sku_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("expected_qty", sa.Integer(), nullable=False),
        sa.Column("counted_qty", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["stocktake_id"],
            ["stocktakes.id"],
            name="fk_stocktake_lines_stocktake_id_stocktakes",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["sku_id"],
            ["skus.id"],
            name="fk_stocktake_lines_sku_id_skus",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_stocktake_lines"),
        sa.UniqueConstraint(
            "stocktake_id",
            "sku_id",
            name="uq_stocktake_lines_stocktake_sku",
        ),
    )


def downgrade() -> None:
    op.drop_table("stocktake_lines")
    op.drop_index("uq_stocktakes_location_in_progress", table_name="stocktakes")
    op.drop_index("ix_stocktakes_created_by_user_id", table_name="stocktakes")
    op.drop_index("ix_stocktakes_location_id", table_name="stocktakes")
    op.drop_table("stocktakes")
