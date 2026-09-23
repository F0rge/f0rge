"""Allow staff to opt a priced SKU into the private commerce projection.

Revision ID: 053_storefront_publication
Revises: 052_lookbook_events
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "053_storefront_publication"
down_revision: Union[str, Sequence[str], None] = "052_lookbook_events"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "skus",
        sa.Column("storefront_published", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("skus", "storefront_published")
