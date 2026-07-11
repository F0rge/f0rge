"""add_treatment_group_name

Revision ID: 012
Revises: 011
Create Date: 2026-07-04 00:00:00.000000

Adds a nullable ``group_name`` column to ``treatments`` so the user can label
related treatment courses (e.g. "SIBO Treatment" containing Rifaximin, Allicin,
a gut motility supplement). Plain free-text label, no FK, no new table -- the
frontend derives distinct group names client-side from the existing list
response.

Nullable add with no default -- safe online migration, no backfill needed.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("treatments", sa.Column("group_name", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("treatments", "group_name")
