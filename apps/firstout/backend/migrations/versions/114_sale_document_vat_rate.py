"""Every sale document keeps the VAT rate it was computed at.

Firstout ADR 0003: reprints, credit notes and conversions use the document's stored rate,
never today's setting. Live documents were all computed at the old hard-coded 1.15, so
0.15 is their historical rate. Archive rows (is_archive) keep Cin7's imported VAT amounts
(some 0% or the pre-April-2018 14%); their 0.15 is nominal. ADD COLUMN ... DEFAULT fills
every row regardless of forced RLS, so no per-team backfill is needed.

The server default stays in this release so the previous release, which does not know the
column, can still insert during the deploy (P-020). A later release may drop it.

Revision ID: 114_sale_document_vat_rate
Revises: 113_sale_line_discount
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "114_sale_document_vat_rate"
down_revision = "113_sale_line_discount"
branch_labels = None
depends_on = None

_TABLES = ("tax_invoices", "credit_notes", "quotes", "sales_orders", "laybys")


def upgrade() -> None:
    for table in _TABLES:
        op.add_column(
            table,
            sa.Column("vat_rate", sa.Numeric(5, 4), nullable=False, server_default=sa.text("0.15")),
        )


def downgrade() -> None:
    for table in _TABLES:
        op.drop_column(table, "vat_rate")
