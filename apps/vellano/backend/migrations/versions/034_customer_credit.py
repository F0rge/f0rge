"""Customer credit limit and on-hold flags.

Revision ID: 034_customer_credit
Revises: 033_roles_permissions
Create Date: 2026-09-02

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "034_customer_credit"
down_revision: Union[str, Sequence[str], None] = "033_roles_permissions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "customers",
        sa.Column("credit_limit", sa.Numeric(14, 2), nullable=True),
    )
    op.add_column(
        "customers",
        sa.Column(
            "on_hold",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "customers",
        sa.Column("on_hold_reason", sa.String(length=512), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("customers", "on_hold_reason")
    op.drop_column("customers", "on_hold")
    op.drop_column("customers", "credit_limit")
