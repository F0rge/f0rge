"""Stockist and decorator ex-VAT prices on SKUs.

Revision ID: 076_sku_price_tiers
Revises: 075_po_pending_skus

Adds two nullable columns. Existing wholesale and retail figures are left
as they are, so till and quote prices do not change.

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


def upgrade() -> None:
    op.add_column(
        "skus",
        sa.Column("stockist_ex_vat", sa.Numeric(precision=12, scale=2), nullable=True),
    )
    op.add_column(
        "skus",
        sa.Column("decorator_ex_vat", sa.Numeric(precision=12, scale=2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("skus", "decorator_ex_vat")
    op.drop_column("skus", "stockist_ex_vat")
