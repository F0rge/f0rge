"""Partial invoice and bill payments.

Revision ID: 070_partial_payments
Revises: 069_warehouse_sales_quotes

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "070_partial_payments"
down_revision: Union[str, Sequence[str], None] = "069_warehouse_sales_quotes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tax_invoices",
        sa.Column(
            "payment_status",
            sa.String(length=32),
            nullable=False,
            server_default="unpaid",
        ),
    )
    op.execute(
        """
        UPDATE tax_invoices
        SET payment_status = CASE
            WHEN amount_paid <= 0 THEN 'unpaid'
            WHEN amount_paid >= total_inc_vat THEN 'paid'
            ELSE 'partially_paid'
        END
        """
    )

    op.add_column(
        "bills",
        sa.Column(
            "payment_status",
            sa.String(length=32),
            nullable=False,
            server_default="unpaid",
        ),
    )
    op.add_column(
        "bills",
        sa.Column(
            "amount_paid_foreign",
            sa.Numeric(precision=14, scale=2),
            nullable=False,
            server_default="0",
        ),
    )
    # Bills could only be unpaid or paid in full before this change.
    op.execute(
        """
        UPDATE bills
        SET amount_paid_foreign = CASE
                WHEN amount_paid_zar >= amount_zar AND amount_zar > 0 THEN amount_foreign
                ELSE 0
            END,
            payment_status = CASE
                WHEN amount_paid_zar <= 0 THEN 'unpaid'
                WHEN amount_paid_zar >= amount_zar THEN 'paid'
                ELSE 'partially_paid'
            END
        """
    )


def downgrade() -> None:
    op.drop_column("bills", "amount_paid_foreign")
    op.drop_column("bills", "payment_status")
    op.drop_column("tax_invoices", "payment_status")
