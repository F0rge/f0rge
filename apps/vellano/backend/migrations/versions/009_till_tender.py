"""S9 till payment tender.

Revision ID: 009_till_tender
Revises: 008_bank_imports
Create Date: 2026-09-01

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "009_till_tender"
down_revision: Union[str, Sequence[str], None] = "008_bank_imports"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "payments",
        sa.Column(
            "tender",
            sa.String(length=8),
            nullable=True,
        ),
    )
    op.create_check_constraint(
        "ck_payments_tender",
        "payments",
        "tender IS NULL OR tender IN ('cash', 'card')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_payments_tender", "payments", type_="check")
    op.drop_column("payments", "tender")
