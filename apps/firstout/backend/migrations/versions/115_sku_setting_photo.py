"""Store the optional setting image separately from the three studio slots.

Revision ID: 115_sku_setting_photo
Revises: 114_sale_document_vat_rate
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "115_sku_setting_photo"
down_revision = "114_sale_document_vat_rate"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("skus", sa.Column("setting_photo_storage_key", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("skus", "setting_photo_storage_key")
