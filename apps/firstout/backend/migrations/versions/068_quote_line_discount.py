"""Per-line percent discount on quotes.

Revision ID: 068_quote_line_discount
Revises: 067_customer_search

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "068_quote_line_discount"
down_revision: Union[str, Sequence[str], None] = "067_customer_search"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "quote_lines",
        sa.Column(
            "discount_percent",
            sa.Numeric(5, 2),
            nullable=False,
            server_default="0",
        ),
    )
    op.create_check_constraint(
        "ck_quote_lines_discount_percent",
        "quote_lines",
        "discount_percent >= 0 AND discount_percent <= 100",
    )


def downgrade() -> None:
    op.drop_constraint("ck_quote_lines_discount_percent", "quote_lines", type_="check")
    op.drop_column("quote_lines", "discount_percent")
