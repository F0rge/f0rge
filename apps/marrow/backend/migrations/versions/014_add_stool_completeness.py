"""add_stool_completeness

Revision ID: 014
Revises: 013
Create Date: 2026-07-08 00:00:00.000000

Adds ``entries.stool_completeness`` -- nullable text, 'complete' | 'incomplete'
| null (unrecorded). Additive and data-preserving: a nullable column with no
backfill, no existing rows touched.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "014"
down_revision: Union[str, None] = "013"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("entries", sa.Column("stool_completeness", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("entries", "stool_completeness")
