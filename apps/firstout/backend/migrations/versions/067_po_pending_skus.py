"""Purchase orders can wait for SKUs before approval.

Revision ID: 067_po_pending_skus
Revises: 066_supplier_invoice_match

Ordering: revises 066_supplier_invoice_match. That revision revises
065_supplier_document_intake, which revises 062_cin7_import.
This chain does not follow 063_customer_search (#877) or
063_quote_line_discount / 064_warehouse_sales_quotes (#878). Those drafts
also branch from 062, so Alembic has more than one head until a merge
revision is added. Apply this chain on a database whose head is 062.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "067_po_pending_skus"
down_revision: Union[str, Sequence[str], None] = "066_supplier_invoice_match"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "purchase_orders", sa.Column("supplier_ref", sa.String(length=128), nullable=True)
    )
    op.add_column("purchase_orders", sa.Column("notes", sa.Text(), nullable=True))
    op.add_column("po_lines", sa.Column("supplier_code", sa.String(length=128), nullable=True))
    op.add_column("po_lines", sa.Column("description", sa.String(length=512), nullable=True))
    op.add_column("po_lines", sa.Column("notes", sa.Text(), nullable=True))
    op.alter_column("po_lines", "sku_id", existing_type=sa.Uuid(), nullable=True)
    op.drop_constraint("uq_po_lines_po_sku", "po_lines", type_="unique")
    op.create_index(
        "uq_po_lines_po_sku",
        "po_lines",
        ["po_id", "sku_id"],
        unique=True,
        postgresql_where=sa.text("sku_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_po_lines_po_sku", table_name="po_lines")
    op.create_unique_constraint("uq_po_lines_po_sku", "po_lines", ["po_id", "sku_id"])
    op.alter_column("po_lines", "sku_id", existing_type=sa.Uuid(), nullable=False)
    op.drop_column("po_lines", "notes")
    op.drop_column("po_lines", "description")
    op.drop_column("po_lines", "supplier_code")
    op.drop_column("purchase_orders", "notes")
    op.drop_column("purchase_orders", "supplier_ref")
