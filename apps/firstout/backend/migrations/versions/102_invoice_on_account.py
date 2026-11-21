"""Mark tax invoices issued on account (pay on statement) so they read "On statement" until paid.

Revision ID: 102_invoice_on_account
Revises: 101_stock_reservation_changes
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "102_invoice_on_account"
down_revision = "101_stock_reservation_changes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tax_invoices",
        sa.Column("on_account", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )


def downgrade() -> None:
    op.drop_column("tax_invoices", "on_account")
