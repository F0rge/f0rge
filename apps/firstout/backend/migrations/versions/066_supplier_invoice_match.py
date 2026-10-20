"""Supplier VAT/address already landed. Invoice match columns.

Revision ID: 066_supplier_invoice_match
Revises: 065_supplier_document_intake

Ordering: revises 065_supplier_document_intake, which itself revises 062.
It does not follow 063_customer_search or 064_warehouse_sales_quotes.

Links a posted supplier bill to the purchase order it was checked against,
stops the same supplier invoice number being filed twice, and stores the
owner switch for posting an exact match without a second click.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "066_supplier_invoice_match"
down_revision: Union[str, Sequence[str], None] = "065_supplier_document_intake"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "team_settings",
        sa.Column(
            "auto_process_exact_supplier_invoices",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "bills",
        sa.Column("purchase_order_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_bills_purchase_order_id",
        "bills",
        "purchase_orders",
        ["purchase_order_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "uq_bills_supplier_ref_ci",
        "bills",
        ["supplier_id", sa.text("lower(supplier_ref)")],
        unique=True,
        postgresql_where=sa.text("btrim(supplier_ref) <> ''"),
    )


def downgrade() -> None:
    op.drop_index("uq_bills_supplier_ref_ci", table_name="bills")
    op.drop_constraint("fk_bills_purchase_order_id", "bills", type_="foreignkey")
    op.drop_column("bills", "purchase_order_id")
    op.drop_column("team_settings", "auto_process_exact_supplier_invoices")
