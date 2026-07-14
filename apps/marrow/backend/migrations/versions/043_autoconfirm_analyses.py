"""auto-confirm legacy analyses

Revision ID: 043
Revises: 042
Create Date: 2026-07-14 00:00:00.000000

Analyses now auto-confirm on completion (the frontend dropped the manual
"Confirm" button). Backfill existing ``complete`` / ``needs_review`` rows to
``confirmed`` so they light up diet-flags, insights, and meals like new ones.
Spans all users, so it runs under the migrator RLS bypass (see 042).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from f0rge_db.rls import migration_bypass

revision: str = "043"
down_revision: Union[str, None] = "042"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    with migration_bypass(bind, ("photo_analyses",)):
        bind.execute(
            sa.text(
                "UPDATE photo_analyses SET status = 'confirmed' "
                "WHERE status IN ('complete', 'needs_review')"
            )
        )


def downgrade() -> None:
    # The complete/needs_review split can't be reconstructed from 'confirmed';
    # this is a lossless forward change, so downgrade is a no-op.
    pass
