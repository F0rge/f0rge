"""add_dietary_confirmed_flags

Revision ID: 017
Revises: 016
Create Date: 2026-07-09 00:00:00.000000

Adds ``photo_analyses.gluten_free_confirmed`` and
``photo_analyses.lactose_free_confirmed`` (non-nullable, default false) so a
user can override the auto-detected dietary scoring per meal: "this dish was
actually gluten-free" suppresses the gluten flag, "lactose-free" drops only the
lactose contribution to high-FODMAP (dairy stays).

Additive/data-preserving: server_default backfills existing rows to false,
no data touched otherwise.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "017"
down_revision: Union[str, None] = "016"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "photo_analyses",
        sa.Column("gluten_free_confirmed", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "photo_analyses",
        sa.Column("lactose_free_confirmed", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("photo_analyses", "lactose_free_confirmed")
    op.drop_column("photo_analyses", "gluten_free_confirmed")
