"""add_treatment_end_reason

Revision ID: 015
Revises: 014
Create Date: 2026-07-09 00:00:00.000000

Adds ``treatments.end_reason`` (nullable, CHECK-constrained to a fixed set)
and ``treatments.end_note`` (nullable free text) so discontinuing a
treatment can record *why*, not just *when*. Mirror the allowed set in
``app.schemas.treatment.TREATMENT_END_REASONS`` -- migrations don't import
app code (see data-engineer/migration_seed_pattern.md), so the CHECK clause
is a separately-maintained literal.

Both columns are additive and data-preserving: nullable, no default, no
backfill, no existing rows touched. Null end_reason on an already-ended
treatment (end_date set) means "ended, unspecified" -- legacy behavior is
unaffected.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "015"
down_revision: Union[str, None] = "014"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None

_END_REASONS = ("completed", "side_effects", "ineffective", "doctor_advised", "switched", "other")


def upgrade() -> None:
    op.add_column("treatments", sa.Column("end_reason", sa.String(), nullable=True))
    op.add_column("treatments", sa.Column("end_note", sa.Text(), nullable=True))
    reasons = ", ".join(f"'{r}'" for r in _END_REASONS)
    op.create_check_constraint(
        "ck_treatments_end_reason",
        "treatments",
        f"end_reason IS NULL OR end_reason IN ({reasons})",
    )


def downgrade() -> None:
    op.drop_constraint("ck_treatments_end_reason", "treatments", type_="check")
    op.drop_column("treatments", "end_note")
    op.drop_column("treatments", "end_reason")
