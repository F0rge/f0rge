"""Widen payments tender check to include EFT.

Revision ID: 021_v2_till_eft_tender
Revises: 020_v2_s12_reorder_min
Create Date: 2026-09-01

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "021_v2_till_eft_tender"
down_revision: Union[str, Sequence[str], None] = "020_v2_s12_reorder_min"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("ck_payments_tender", "payments", type_="check")
    op.create_check_constraint(
        "ck_payments_tender",
        "payments",
        "tender IS NULL OR tender IN ('cash', 'card', 'deposit', 'eft')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_payments_tender", "payments", type_="check")
    op.create_check_constraint(
        "ck_payments_tender",
        "payments",
        "tender IS NULL OR tender IN ('cash', 'card', 'deposit')",
    )
