"""purchase orders, landing bills, inventory stock tables.

Revision ID: 005_purchase_orders
Revises: 004_catalogue
Create Date: 2026-09-01

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "005_purchase_orders"
down_revision: Union[str, Sequence[str], None] = "004_catalogue"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "purchase_orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("po_number", sa.String(length=32), nullable=False),
        sa.Column("supplier_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("proforma_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="open",
        ),
        sa.Column("fx_to_zar", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("received_location_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["supplier_id"],
            ["suppliers.id"],
            name="fk_purchase_orders_supplier_id_suppliers",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["proforma_id"],
            ["proformas.id"],
            name="fk_purchase_orders_proforma_id_proformas",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["received_location_id"],
            ["locations.id"],
            name="fk_purchase_orders_received_location_id_locations",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_purchase_orders"),
        sa.UniqueConstraint("po_number", name="uq_purchase_orders_po_number"),
        sa.CheckConstraint(
            "status IN ('open', 'on_water', 'landed', 'received')",
            name="ck_purchase_orders_status",
        ),
    )
    op.create_index("ix_purchase_orders_supplier_id", "purchase_orders", ["supplier_id"])

    op.create_table(
        "po_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("po_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sku_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("qty", sa.Integer(), nullable=False),
        sa.Column("factory_unit_amount", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("unit_cost_zar", sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["po_id"],
            ["purchase_orders.id"],
            name="fk_po_lines_po_id_purchase_orders",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["sku_id"],
            ["skus.id"],
            name="fk_po_lines_sku_id_skus",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_po_lines"),
        sa.UniqueConstraint("po_id", "sku_id", name="uq_po_lines_po_sku"),
        sa.CheckConstraint("qty >= 1", name="ck_po_lines_qty"),
        sa.CheckConstraint("factory_unit_amount > 0", name="ck_po_lines_factory_unit_amount"),
    )
    op.create_index("ix_po_lines_po_id", "po_lines", ["po_id"])
    op.create_index("ix_po_lines_sku_id", "po_lines", ["sku_id"])

    op.create_table(
        "landing_bills",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("po_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("invoice_number", sa.String(length=64), nullable=False),
        sa.Column("amount", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("pdf_storage_key", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["po_id"],
            ["purchase_orders.id"],
            name="fk_landing_bills_po_id_purchase_orders",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_landing_bills"),
        sa.UniqueConstraint("po_id", "kind", name="uq_landing_bills_po_kind"),
        sa.CheckConstraint(
            "kind IN ('factory', 'freight', 'clearance')",
            name="ck_landing_bills_kind",
        ),
        sa.CheckConstraint("amount > 0", name="ck_landing_bills_amount"),
    )
    op.create_index("ix_landing_bills_po_id", "landing_bills", ["po_id"])

    op.create_table(
        "sku_stock",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sku_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("on_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["sku_id"],
            ["skus.id"],
            name="fk_sku_stock_sku_id_skus",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_sku_stock"),
        sa.UniqueConstraint("sku_id", name="uq_sku_stock_sku_id"),
        sa.CheckConstraint("on_order >= 0", name="ck_sku_stock_on_order"),
    )

    op.create_table(
        "location_stock",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sku_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("location_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("on_hand", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unit_cost_zar", sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["sku_id"],
            ["skus.id"],
            name="fk_location_stock_sku_id_skus",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["location_id"],
            ["locations.id"],
            name="fk_location_stock_location_id_locations",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_location_stock"),
        sa.UniqueConstraint("sku_id", "location_id", name="uq_location_stock_sku_location"),
        sa.CheckConstraint("on_hand >= 0", name="ck_location_stock_on_hand"),
    )
    op.create_index("ix_location_stock_sku_id", "location_stock", ["sku_id"])
    op.create_index("ix_location_stock_location_id", "location_stock", ["location_id"])


def downgrade() -> None:
    op.drop_index("ix_location_stock_location_id", table_name="location_stock")
    op.drop_index("ix_location_stock_sku_id", table_name="location_stock")
    op.drop_table("location_stock")
    op.drop_table("sku_stock")
    op.drop_index("ix_landing_bills_po_id", table_name="landing_bills")
    op.drop_table("landing_bills")
    op.drop_index("ix_po_lines_sku_id", table_name="po_lines")
    op.drop_index("ix_po_lines_po_id", table_name="po_lines")
    op.drop_table("po_lines")
    op.drop_index("ix_purchase_orders_supplier_id", table_name="purchase_orders")
    op.drop_table("purchase_orders")
