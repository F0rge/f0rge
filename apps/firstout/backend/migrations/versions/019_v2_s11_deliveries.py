"""V2-S11 outbound deliveries.

Revision ID: 019_v2_s11_deliveries
Revises: 018_v2_s13_sku_supplier
Create Date: 2026-09-01

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "019_v2_s11_deliveries"
down_revision: Union[str, Sequence[str], None] = "018_v2_s13_sku_supplier"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "deliveries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("delivery_number", sa.Text(), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("layby_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("location_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("delivery_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["invoice_id"],
            ["tax_invoices.id"],
            name="fk_deliveries_invoice_id_tax_invoices",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["layby_id"],
            ["laybys.id"],
            name="fk_deliveries_layby_id_laybys",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["location_id"],
            ["locations.id"],
            name="fk_deliveries_location_id_locations",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name="fk_deliveries_created_by_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_deliveries"),
        sa.UniqueConstraint("delivery_number", name="uq_deliveries_delivery_number"),
        sa.CheckConstraint(
            "(source_type = 'invoice' AND invoice_id IS NOT NULL AND layby_id IS NULL) "
            "OR (source_type = 'layby' AND layby_id IS NOT NULL AND invoice_id IS NULL)",
            name="ck_deliveries_source",
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'packed', 'delivered', 'cancelled')",
            name="ck_deliveries_status",
        ),
    )
    op.create_index("ix_deliveries_invoice_id", "deliveries", ["invoice_id"])
    op.create_index("ix_deliveries_layby_id", "deliveries", ["layby_id"])
    op.create_index("ix_deliveries_location_id", "deliveries", ["location_id"])
    op.create_index(
        "ix_deliveries_created_by_user_id",
        "deliveries",
        ["created_by_user_id"],
    )
    op.create_index(
        "uq_deliveries_invoice_active",
        "deliveries",
        ["invoice_id"],
        unique=True,
        postgresql_where=sa.text("invoice_id IS NOT NULL AND status != 'cancelled'"),
    )
    op.create_index(
        "uq_deliveries_layby_active",
        "deliveries",
        ["layby_id"],
        unique=True,
        postgresql_where=sa.text("layby_id IS NOT NULL AND status != 'cancelled'"),
    )

    op.create_table(
        "delivery_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("delivery_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sku_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("qty", sa.Integer(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["delivery_id"],
            ["deliveries.id"],
            name="fk_delivery_lines_delivery_id_deliveries",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["sku_id"],
            ["skus.id"],
            name="fk_delivery_lines_sku_id_skus",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_delivery_lines"),
        sa.CheckConstraint("qty > 0", name="ck_delivery_lines_qty"),
    )
    op.create_index("ix_delivery_lines_delivery_id", "delivery_lines", ["delivery_id"])


def downgrade() -> None:
    op.drop_index("ix_delivery_lines_delivery_id", table_name="delivery_lines")
    op.drop_table("delivery_lines")
    op.drop_index("uq_deliveries_layby_active", table_name="deliveries")
    op.drop_index("uq_deliveries_invoice_active", table_name="deliveries")
    op.drop_index("ix_deliveries_created_by_user_id", table_name="deliveries")
    op.drop_index("ix_deliveries_location_id", table_name="deliveries")
    op.drop_index("ix_deliveries_layby_id", table_name="deliveries")
    op.drop_index("ix_deliveries_invoice_id", table_name="deliveries")
    op.drop_table("deliveries")
