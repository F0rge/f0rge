"""Optional category filter on a stocktake.

Revision ID: 063_stocktake_category
Revises: 062_drop_nia_lookbooks

Null means the count covers every SKU. A value is a case-insensitive match
on skus.category.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "063_stocktake_category"
down_revision: Union[str, Sequence[str], None] = "062_drop_nia_lookbooks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("stocktakes", sa.Column("category", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("stocktakes", "category")
