"""SKU price tiers and customer price classification.

Revision ID: 076_sku_price_tiers
Revises: 075_po_pending_skus

Adds stockist and decorator ex-VAT columns on SKUs. Adds
customers.price_classification (Stockist, Wholesale, Decorator, Retail).
Existing trade customers become Wholesale. Everyone else becomes Retail.
customer_type and price_tier stay, so nothing already stored is deleted.

Line warnings and a document display flag are additive. Issued invoice
amounts are not rewritten.

This revision follows 075_po_pending_skus from release/firstout-main-oct21.
Merge that release before this one. On main alone, 075 is not in the tree yet.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "076_sku_price_tiers"
down_revision: Union[str, Sequence[str], None] = "075_po_pending_skus"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_LEGACY_CLASSIFICATION_SQL = """
UPDATE customers
SET price_classification = CASE
    WHEN customer_type = 'trade' THEN 'Wholesale'
    ELSE 'Retail'
END
"""

_DOCUMENT_BASIS_SQL = """
UPDATE {table} AS doc
SET prices_include_vat = (c.price_classification = 'Retail')
FROM customers AS c
WHERE c.id = doc.customer_id
"""


def upgrade() -> None:
    op.add_column(
        "skus",
        sa.Column("stockist_ex_vat", sa.Numeric(precision=12, scale=2), nullable=True),
    )
    op.add_column(
        "skus",
        sa.Column("decorator_ex_vat", sa.Numeric(precision=12, scale=2), nullable=True),
    )
    op.add_column(
        "customers",
        sa.Column(
            "price_classification",
            sa.String(length=32),
            nullable=False,
            server_default="Retail",
        ),
    )
    op.execute(_LEGACY_CLASSIFICATION_SQL)
    op.create_check_constraint(
        "ck_customers_price_classification",
        "customers",
        "price_classification IN ('Stockist', 'Wholesale', 'Decorator', 'Retail')",
    )
    for table in ("quote_lines", "sales_order_lines", "invoice_lines"):
        op.add_column(table, sa.Column("price_warning", sa.Text(), nullable=True))
    for table in ("quotes", "sales_orders", "tax_invoices"):
        op.add_column(
            table,
            sa.Column(
                "prices_include_vat",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            ),
        )
        op.execute(_DOCUMENT_BASIS_SQL.format(table=table))


def downgrade() -> None:
    for table in ("tax_invoices", "sales_orders", "quotes"):
        op.drop_column(table, "prices_include_vat")
    for table in ("invoice_lines", "sales_order_lines", "quote_lines"):
        op.drop_column(table, "price_warning")
    op.drop_constraint("ck_customers_price_classification", "customers", type_="check")
    op.drop_column("customers", "price_classification")
    op.drop_column("skus", "decorator_ex_vat")
    op.drop_column("skus", "stockist_ex_vat")
