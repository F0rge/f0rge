"""Let staff hide a SKU from the shop.

Revision ID: 110_sku_storefront_hidden
Revises: 109_document_template
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "110_sku_storefront_hidden"
down_revision = "109_document_template"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "skus",
        sa.Column("storefront_hidden", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("skus", "storefront_hidden")
