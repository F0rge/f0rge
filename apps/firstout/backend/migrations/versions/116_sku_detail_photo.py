"""Store the optional detail image separately from the other gallery slots.

Revision ID: 116_sku_detail_photo
Revises: 115_sku_setting_photo
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "116_sku_detail_photo"
down_revision = "115_sku_setting_photo"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("skus", sa.Column("detail_photo_storage_key", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("skus", "detail_photo_storage_key")
