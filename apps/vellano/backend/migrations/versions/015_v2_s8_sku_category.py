"""V2-S8 SKU category column.

Revision ID: 015_v2_s8_sku_category
Revises: 014_v2_s6_laybys
Create Date: 2026-09-01

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "015_v2_s8_sku_category"
down_revision: Union[str, Sequence[str], None] = "014_v2_s6_laybys"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("skus", sa.Column("category", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("skus", "category")
