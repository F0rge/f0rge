"""sku wholesale and retail ex-vat price columns.

Revision ID: 006_sku_prices
Revises: 005_purchase_orders
Create Date: 2026-09-01

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006_sku_prices"
down_revision: Union[str, Sequence[str], None] = "005_purchase_orders"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "skus",
        sa.Column("wholesale_ex_vat", sa.Numeric(precision=12, scale=2), nullable=True),
    )
    op.add_column(
        "skus",
        sa.Column("retail_ex_vat", sa.Numeric(precision=12, scale=2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("skus", "retail_ex_vat")
    op.drop_column("skus", "wholesale_ex_vat")
