"""add_protocol_adherence

Revision ID: 013
Revises: 012
Create Date: 2026-07-08 00:00:00.000000

Adds per-dose protocol adherence tracking for the SIBO-protocol "Today's
Protocol" card:

1. ``treatments.doses_per_day`` -- nullable int, 1..12. Null means the
   treatment is not dose-tracked (e.g. "Low FODMAP diet"), so it never
   contributes to the daily dose count or the streak.

2. ``treatment_log`` -- one row per (treatment, date) holding that day's
   dose count, mirroring the existing ``tracker`` / ``tracker_log`` shape
   (composite PK, FK ON DELETE CASCADE, ``date`` index).

Both changes are additive and data-preserving: a nullable column with no
backfill, and a brand-new table with no existing rows to migrate.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "013"
down_revision: Union[str, None] = "012"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("treatments", sa.Column("doses_per_day", sa.Integer(), nullable=True))
    op.create_check_constraint(
        "ck_treatments_doses_per_day_range",
        "treatments",
        "doses_per_day IS NULL OR (doses_per_day BETWEEN 1 AND 12)",
    )

    op.create_table(
        "treatment_log",
        sa.Column("treatment_id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("doses_taken", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("treatment_id", "date", name="pk_treatment_log"),
        sa.ForeignKeyConstraint(
            ["treatment_id"],
            ["treatments.id"],
            ondelete="CASCADE",
            name="fk_treatment_log_treatment_id",
        ),
    )
    op.create_index("ix_treatment_log_date", "treatment_log", ["date"])


def downgrade() -> None:
    op.drop_index("ix_treatment_log_date", table_name="treatment_log")
    op.drop_table("treatment_log")
    op.drop_constraint("ck_treatments_doses_per_day_range", "treatments", type_="check")
    op.drop_column("treatments", "doses_per_day")
