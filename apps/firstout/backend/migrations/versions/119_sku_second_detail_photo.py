"""Store the optional second detail image in its own gallery slot.

Revision ID: 119_sku_second_detail_photo
Revises: 118_sku_retail_precision
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "119_sku_second_detail_photo"
down_revision = "118_sku_retail_precision"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("skus", sa.Column("second_detail_photo_storage_key", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("skus", "second_detail_photo_storage_key")
