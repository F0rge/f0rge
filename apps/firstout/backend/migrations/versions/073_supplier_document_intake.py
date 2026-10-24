"""Supplier VAT/address and purchase-order intake snapshot.

Revision ID: 073_supplier_document_intake
Revises: 072_bank_document_match

Stores the supplier particulars a proforma reader can match on, and the
charges / VAT / terms captured when a proforma becomes a purchase order.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "073_supplier_document_intake"
down_revision: Union[str, Sequence[str], None] = "072_bank_document_match"
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
