"""Add opt-in non-stock till service sales and snapshot the setting on invoice lines.

Revision ID: 092_till_no_stock_required
Revises: 091_sku_archive
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "092_till_no_stock_required"
down_revision = "091_sku_archive"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("skus", "invoice_lines"):
        op.add_column(
            table,
            sa.Column(
                "till_no_stock_required", sa.Boolean(), nullable=False, server_default=sa.false()
            ),
        )


def downgrade() -> None:
    # Retain the snapshot during application rollbacks. Dropping it loses the
    # ability to distinguish service sales from stocked sales during returns.
    for table in ("invoice_lines", "skus"):
        op.drop_column(table, "till_no_stock_required")
