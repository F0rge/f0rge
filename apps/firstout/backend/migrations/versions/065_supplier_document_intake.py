"""Supplier VAT/address and purchase-order intake snapshot.

Revision ID: 065_supplier_document_intake
Revises: 062_cin7_import

Ordering: this revises 062_cin7_import and does not follow the other open drafts
063_customer_search (#877) or 063_quote_line_discount / 064_warehouse_sales_quotes (#878).
Those also branch from 062, so Alembic will have more than one head until a merge
revision is added. Apply this chain on a database whose head is 062.

Stores the supplier particulars a proforma reader can match on, and the
charges / VAT / terms captured when a proforma becomes a purchase order.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "065_supplier_document_intake"
down_revision: Union[str, Sequence[str], None] = "062_cin7_import"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("suppliers", sa.Column("vat_number", sa.String(length=64), nullable=True))
    op.add_column("suppliers", sa.Column("address", sa.Text(), nullable=True))
    op.create_index("ix_suppliers_vat_number", "suppliers", ["vat_number"])
    op.add_column(
        "purchase_orders",
        sa.Column("intake_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("purchase_orders", "intake_snapshot")
    op.drop_index("ix_suppliers_vat_number", table_name="suppliers")
    op.drop_column("suppliers", "address")
    op.drop_column("suppliers", "vat_number")
