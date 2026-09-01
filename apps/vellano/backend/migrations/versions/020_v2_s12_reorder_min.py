"""V2-S12 reorder minimum on SKUs.

Revision ID: 020_v2_s12_reorder_min
Revises: 019_v2_s11_deliveries
Create Date: 2026-09-01

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "020_v2_s12_reorder_min"
down_revision: Union[str, Sequence[str], None] = "019_v2_s11_deliveries"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("skus", sa.Column("reorder_min", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("skus", "reorder_min")
