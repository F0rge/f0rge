"""Printed and internal notes on tax invoices, carried by till baskets and held sales.

Revision ID: 103_invoice_notes
Revises: 102_invoice_on_account
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "103_invoice_notes"
down_revision = "102_invoice_on_account"
branch_labels = None
depends_on = None

_TABLES = ("tax_invoices", "till_baskets", "held_sales")
_COLUMNS = ("note_printed", "note_internal")


def upgrade() -> None:
    for table in _TABLES:
        for column in _COLUMNS:
            op.add_column(table, sa.Column(column, sa.Text(), nullable=True))


def downgrade() -> None:
    for table in _TABLES:
        for column in _COLUMNS:
            op.drop_column(table, column)
