"""SKU carton_count (pattern A) and virtual kit BOM (pattern B).

Revision ID: 030_sku_carton_bom
Revises: 029_warehouse_bins
Create Date: 2026-09-01

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "030_sku_carton_bom"
down_revision: Union[str, Sequence[str], None] = "029_warehouse_bins"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "skus",
        sa.Column("carton_count", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_check_constraint("ck_skus_carton_count", "skus", "carton_count >= 1")

    op.create_table(
        "sku_bom_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parent_sku_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("component_sku_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("qty", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["parent_sku_id"],
            ["skus.id"],
            name="fk_sku_bom_lines_parent_sku_id_skus",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["component_sku_id"],
            ["skus.id"],
            name="fk_sku_bom_lines_component_sku_id_skus",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "parent_sku_id",
            "component_sku_id",
            name="uq_sku_bom_lines_parent_component",
        ),
        sa.CheckConstraint("qty >= 1", name="ck_sku_bom_lines_qty"),
        sa.CheckConstraint(
            "parent_sku_id <> component_sku_id",
            name="ck_sku_bom_lines_no_self_parent",
        ),
    )
    op.create_index(
        "ix_sku_bom_lines_parent_sku_id",
        "sku_bom_lines",
        ["parent_sku_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_sku_bom_lines_parent_sku_id", table_name="sku_bom_lines")
    op.drop_table("sku_bom_lines")
    op.drop_constraint("ck_skus_carton_count", "skus", type_="check")
    op.drop_column("skus", "carton_count")
