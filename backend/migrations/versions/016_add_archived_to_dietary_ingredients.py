"""add_archived_to_dietary_ingredients

Revision ID: 016
Revises: 015
Create Date: 2026-07-09 00:00:00.000000

Adds ``dietary_ingredients.archived`` (non-nullable, default false) so the
new Ingredients manager CRUD can hide catalog rows from pickers without
deleting them -- same convention as ``supplement_catalog``/``diet_tag_catalog``.

Additive/data-preserving: server_default backfills existing rows to false,
no data touched otherwise.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "016"
down_revision: Union[str, None] = "015"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "dietary_ingredients",
        sa.Column("archived", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("dietary_ingredients", "archived")
