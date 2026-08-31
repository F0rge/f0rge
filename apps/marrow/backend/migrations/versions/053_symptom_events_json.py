"""symptom events json

Revision ID: 053
Revises: 052
Create Date: 2026-08-31 16:20:00.000000

Timed symptom stamps on the daily log. ``symptoms_json`` stays the day's
current score; ``symptom_events_json`` is the clock (same shape as
``medications_json``).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "053"
down_revision: Union[str, None] = "052"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "entries",
        sa.Column(
            "symptom_events_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("entries", "symptom_events_json")
