"""V2-S9 till line discount and deposit tender.

Revision ID: 016_v2_s9_till_discount
Revises: 015_v2_s8_sku_category
Create Date: 2026-09-01

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "016_v2_s9_till_discount"
down_revision: Union[str, Sequence[str], None] = "015_v2_s8_sku_category"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("ck_payments_tender", "payments", type_="check")
    op.create_check_constraint(
        "ck_payments_tender",
        "payments",
        "tender IS NULL OR tender IN ('cash', 'card', 'deposit')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_payments_tender", "payments", type_="check")
    op.create_check_constraint(
        "ck_payments_tender",
        "payments",
        "tender IS NULL OR tender IN ('cash', 'card')",
    )
