"""Split bank lines across invoice and bill payments.

Revision ID: 064_bank_document_match
Revises: 063_partial_payments

Stacked on the partial-payments branch, independently of payment reminders.
That branch also adds a revision 064, so these two are sibling Alembic heads
until one is renumbered when they merge.

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "064_bank_document_match"
down_revision: Union[str, Sequence[str], None] = "063_partial_payments"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "bank_import_line_allocations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("line_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("amount_zar", sa.Numeric(14, 2), nullable=False),
        sa.Column("document_number", sa.String(length=128), nullable=False),
        sa.ForeignKeyConstraint(["line_id"], ["bank_import_lines.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["payment_id"], ["payments.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "line_id",
            "payment_id",
            name="uq_bank_import_line_allocations_line_payment",
        ),
    )
    op.create_index(
        "ix_bank_import_line_allocations_line_id",
        "bank_import_line_allocations",
        ["line_id"],
    )
    op.create_index(
        "ix_bank_import_line_allocations_payment_id",
        "bank_import_line_allocations",
        ["payment_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_bank_import_line_allocations_payment_id",
        table_name="bank_import_line_allocations",
    )
    op.drop_index(
        "ix_bank_import_line_allocations_line_id",
        table_name="bank_import_line_allocations",
    )
    op.drop_table("bank_import_line_allocations")
