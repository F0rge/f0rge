"""Cin7 import: archive documents, reference tables, wider natural keys.

Revision ID: 064_cin7_import
Revises: 063_stocktake_category

Applied here because the importer writes these columns and tables.

Not applied (human sign-off before a follow-up migration):

- ``sku_bom_lines.qty`` is an integer >= 1. Cin7 assembly quantities include
  fractions (fabric metres). Changing the column to numeric would also change
  kit pick and till consumption, which still multiply by an integer.
- Child tables for extra customer contacts/addresses and for supplier
  contacts/addresses. The importer keeps one phone, email, and billing
  address on the customer and does not store supplier contacts.
- A Cin7 price-tier name map (Wholesale / Decorator / Retail / Stockist to
  PriceTier1..10). The product export numbers the tiers and does not name them.

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "064_cin7_import"
down_revision: Union[str, Sequence[str], None] = "063_stocktake_category"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "skus",
        "supplier_ref",
        existing_type=sa.String(length=64),
        type_=sa.String(length=128),
        existing_nullable=True,
    )
    op.alter_column(
        "bills",
        "bill_number",
        existing_type=sa.String(length=32),
        type_=sa.String(length=128),
        existing_nullable=False,
    )
    op.create_index(
        "ix_customers_name_lower",
        "customers",
        [sa.text("lower(name)")],
        unique=True,
    )
    for table in ("sales_orders", "tax_invoices", "purchase_orders", "bills"):
        op.add_column(
            table,
            sa.Column(
                "is_archive",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )

    op.create_table(
        "payment_terms",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("method", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("due_next_month", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_payment_terms_name"),
    )
    op.create_table(
        "tax_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("tax_code", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("account_code", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("inclusive", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("percent", sa.Numeric(8, 2), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_tax_rules_name"),
    )
    op.create_table(
        "sku_supplier_prices",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("sku_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("supplier_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("supplier_sku", sa.String(length=128), nullable=True),
        sa.Column("latest_price", sa.Numeric(18, 4), nullable=True),
        sa.Column("fixed_price", sa.Numeric(18, 4), nullable=True),
        sa.ForeignKeyConstraint(["sku_id"], ["skus.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sku_id", "supplier_id", name="uq_sku_supplier_prices_sku_supplier"),
    )


def downgrade() -> None:
    op.drop_table("sku_supplier_prices")
    op.drop_table("tax_rules")
    op.drop_table("payment_terms")
    for table in ("bills", "purchase_orders", "tax_invoices", "sales_orders"):
        op.drop_column(table, "is_archive")
    op.drop_index("ix_customers_name_lower", table_name="customers")
    op.alter_column(
        "bills",
        "bill_number",
        existing_type=sa.String(length=128),
        type_=sa.String(length=32),
        existing_nullable=False,
    )
    op.alter_column(
        "skus",
        "supplier_ref",
        existing_type=sa.String(length=128),
        type_=sa.String(length=64),
        existing_nullable=True,
    )
