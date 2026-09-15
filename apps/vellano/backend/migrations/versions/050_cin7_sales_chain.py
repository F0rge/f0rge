"""Cin7 sales chain: quotes, sales orders, pick/delivery SO source, portal users.

Revision ID: 050_cin7_sales_chain
Revises: 049_comms_whatsapp
Create Date: 2026-09-15

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "050_cin7_sales_chain"
down_revision: Union[str, Sequence[str], None] = "049_comms_whatsapp"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "quotes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("quote_number", sa.Text(), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("subtotal_ex_vat", sa.Numeric(14, 2), nullable=False),
        sa.Column("vat_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("total_inc_vat", sa.Numeric(14, 2), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('draft', 'sent', 'accepted', 'expired', 'cancelled')",
            name="ck_quotes_status",
        ),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("quote_number", name="uq_quotes_quote_number"),
    )
    op.create_index("ix_quotes_customer_id", "quotes", ["customer_id"])
    op.create_index("ix_quotes_created_by_user_id", "quotes", ["created_by_user_id"])

    op.create_table(
        "quote_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("quote_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sku_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("qty", sa.Integer(), nullable=False),
        sa.Column("unit_ex_vat", sa.Numeric(14, 2), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.CheckConstraint("qty > 0", name="ck_quote_lines_qty"),
        sa.ForeignKeyConstraint(["quote_id"], ["quotes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sku_id"], ["skus.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_quote_lines_quote_id", "quote_lines", ["quote_id"])

    op.create_table(
        "sales_orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("so_number", sa.Text(), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quote_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("location_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("hold_stock", sa.Boolean(), nullable=False),
        sa.Column("awaiting_stock", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("subtotal_ex_vat", sa.Numeric(14, 2), nullable=False),
        sa.Column("vat_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("total_inc_vat", sa.Numeric(14, 2), nullable=False),
        sa.Column("amount_paid", sa.Numeric(14, 2), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('draft', 'open', 'awaiting_stock', 'invoiced', 'cancelled')",
            name="ck_sales_orders_status",
        ),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["quote_id"], ["quotes.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["invoice_id"], ["tax_invoices.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("so_number", name="uq_sales_orders_so_number"),
    )
    op.create_index("ix_sales_orders_customer_id", "sales_orders", ["customer_id"])
    op.create_index("ix_sales_orders_quote_id", "sales_orders", ["quote_id"])
    op.create_index("ix_sales_orders_location_id", "sales_orders", ["location_id"])
    op.create_index("ix_sales_orders_invoice_id", "sales_orders", ["invoice_id"])
    op.create_index("ix_sales_orders_created_by_user_id", "sales_orders", ["created_by_user_id"])

    op.create_table(
        "sales_order_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("sales_order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sku_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("qty", sa.Integer(), nullable=False),
        sa.Column("unit_ex_vat", sa.Numeric(14, 2), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("held_qty", sa.Integer(), nullable=False),
        sa.Column("hold_location_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("hold_unit_cost_zar", sa.Numeric(18, 4), nullable=True),
        sa.CheckConstraint("qty > 0", name="ck_sales_order_lines_qty"),
        sa.CheckConstraint("held_qty >= 0", name="ck_sales_order_lines_held_qty"),
        sa.ForeignKeyConstraint(["sales_order_id"], ["sales_orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sku_id"], ["skus.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["hold_location_id"], ["locations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sales_order_lines_sales_order_id", "sales_order_lines", ["sales_order_id"])

    op.create_table(
        "sales_order_payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("sales_order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("tender", sa.Text(), nullable=False),
        sa.Column("paid_on", sa.Date(), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_sales_order_payments_amount"),
        sa.CheckConstraint("tender IN ('cash', 'eft')", name="ck_sales_order_payments_tender"),
        sa.ForeignKeyConstraint(["sales_order_id"], ["sales_orders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_sales_order_payments_sales_order_id",
        "sales_order_payments",
        ["sales_order_id"],
    )

    op.create_table(
        "customer_portal_users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_disabled", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_customer_portal_users_email"),
    )
    op.create_index(
        "ix_customer_portal_users_customer_id", "customer_portal_users", ["customer_id"]
    )

    op.drop_constraint("ck_picks_kit_qty", "picks", type_="check")
    op.drop_constraint("ck_picks_source_type", "picks", type_="check")
    op.alter_column(
        "picks", "kit_sku_id", existing_type=postgresql.UUID(as_uuid=True), nullable=True
    )
    op.alter_column("picks", "kit_qty", existing_type=sa.Integer(), nullable=True)
    op.add_column(
        "picks",
        sa.Column("sales_order_line_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_picks_sales_order_line_id",
        "picks",
        "sales_order_lines",
        ["sales_order_line_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_picks_sales_order_line_id", "picks", ["sales_order_line_id"])
    op.create_index(
        "uq_picks_sales_order_line_active",
        "picks",
        ["sales_order_line_id"],
        unique=True,
        postgresql_where=sa.text("sales_order_line_id IS NOT NULL AND status != 'cancelled'"),
    )
    op.create_check_constraint(
        "ck_picks_kit_header",
        "picks",
        "(kit_sku_id IS NULL AND kit_qty IS NULL) OR "
        "(kit_sku_id IS NOT NULL AND kit_qty IS NOT NULL AND kit_qty > 0)",
    )
    op.create_check_constraint(
        "ck_picks_source_type",
        "picks",
        "source_type IN ('invoice', 'layby', 'till', 'sales_order')",
    )

    op.drop_constraint("ck_deliveries_source", "deliveries", type_="check")
    op.drop_constraint("ck_deliveries_status", "deliveries", type_="check")
    op.add_column(
        "deliveries",
        sa.Column("sales_order_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column("deliveries", sa.Column("carton_count", sa.Integer(), nullable=True))
    op.add_column("deliveries", sa.Column("loaded_at", sa.DateTime(), nullable=True))
    op.add_column("deliveries", sa.Column("tracking_number", sa.Text(), nullable=True))
    op.add_column("deliveries", sa.Column("carrier", sa.Text(), nullable=True))
    op.create_foreign_key(
        "fk_deliveries_sales_order_id",
        "deliveries",
        "sales_orders",
        ["sales_order_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_deliveries_sales_order_id", "deliveries", ["sales_order_id"])
    op.create_index(
        "uq_deliveries_sales_order_active",
        "deliveries",
        ["sales_order_id"],
        unique=True,
        postgresql_where=sa.text("sales_order_id IS NOT NULL AND status != 'cancelled'"),
    )
    op.create_check_constraint(
        "ck_deliveries_source",
        "deliveries",
        "(source_type = 'invoice' AND invoice_id IS NOT NULL "
        "AND layby_id IS NULL AND sales_order_id IS NULL) "
        "OR (source_type = 'layby' AND layby_id IS NOT NULL "
        "AND invoice_id IS NULL AND sales_order_id IS NULL) "
        "OR (source_type = 'sales_order' AND sales_order_id IS NOT NULL "
        "AND invoice_id IS NULL AND layby_id IS NULL)",
    )
    op.create_check_constraint(
        "ck_deliveries_status",
        "deliveries",
        "status IN ('draft', 'packed', 'loaded', 'delivered', 'cancelled')",
    )

    op.execute(
        """
        INSERT INTO document_sequences (
            id, team_id, doc_type, prefix, padding, next_value, created_at, updated_at
        )
        SELECT gen_random_uuid(), teams.id, seeds.doc_type, seeds.prefix, 4, 1, NOW(), NOW()
        FROM teams
        CROSS JOIN (
            VALUES ('quote', 'QT'), ('sales_order', 'SO')
        ) AS seeds(doc_type, prefix)
        ON CONFLICT (team_id, doc_type) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_constraint("ck_deliveries_status", "deliveries", type_="check")
    op.drop_constraint("ck_deliveries_source", "deliveries", type_="check")
    op.drop_index("uq_deliveries_sales_order_active", table_name="deliveries")
    op.drop_index("ix_deliveries_sales_order_id", table_name="deliveries")
    op.drop_constraint("fk_deliveries_sales_order_id", "deliveries", type_="foreignkey")
    op.drop_column("deliveries", "carrier")
    op.drop_column("deliveries", "tracking_number")
    op.drop_column("deliveries", "loaded_at")
    op.drop_column("deliveries", "carton_count")
    op.drop_column("deliveries", "sales_order_id")
    op.create_check_constraint(
        "ck_deliveries_source",
        "deliveries",
        "(source_type = 'invoice' AND invoice_id IS NOT NULL AND layby_id IS NULL) "
        "OR (source_type = 'layby' AND layby_id IS NOT NULL AND invoice_id IS NULL)",
    )
    op.create_check_constraint(
        "ck_deliveries_status",
        "deliveries",
        "status IN ('draft', 'packed', 'delivered', 'cancelled')",
    )

    op.drop_constraint("ck_picks_source_type", "picks", type_="check")
    op.drop_constraint("ck_picks_kit_header", "picks", type_="check")
    op.drop_index("uq_picks_sales_order_line_active", table_name="picks")
    op.drop_index("ix_picks_sales_order_line_id", table_name="picks")
    op.drop_constraint("fk_picks_sales_order_line_id", "picks", type_="foreignkey")
    op.drop_column("picks", "sales_order_line_id")
    op.alter_column("picks", "kit_qty", existing_type=sa.Integer(), nullable=False)
    op.alter_column(
        "picks", "kit_sku_id", existing_type=postgresql.UUID(as_uuid=True), nullable=False
    )
    op.create_check_constraint("ck_picks_kit_qty", "picks", "kit_qty > 0")
    op.create_check_constraint(
        "ck_picks_source_type",
        "picks",
        "source_type IN ('invoice', 'layby', 'till')",
    )

    op.drop_table("customer_portal_users")
    op.drop_table("sales_order_payments")
    op.drop_table("sales_order_lines")
    op.drop_table("sales_orders")
    op.drop_table("quote_lines")
    op.drop_table("quotes")
    op.execute("DELETE FROM document_sequences WHERE doc_type IN ('quote', 'sales_order')")
