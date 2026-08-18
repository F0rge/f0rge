"""nullable core scales

Revision ID: 052
Revises: 051
Create Date: 2026-08-18 15:40:00.000000

Wellbeing / gut core scales start unset on a new day. NULL means "not rated"
(distinct from bloating=0 / None). Signals already skip missing overall.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "052"
down_revision: Union[str, None] = "051"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COLS = ("overall", "bloating", "sleep_quality", "stress")


def upgrade() -> None:
    for col in _COLS:
        op.alter_column("entries", col, existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            UPDATE entries SET
              overall = COALESCE(overall, 2),
              bloating = COALESCE(bloating, 0),
              sleep_quality = COALESCE(sleep_quality, 2),
              stress = COALESCE(stress, 1)
            """
        )
    )
    for col in _COLS:
        op.alter_column("entries", col, existing_type=sa.Integer(), nullable=False)
