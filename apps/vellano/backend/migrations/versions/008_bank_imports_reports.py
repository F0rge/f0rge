"""S7 bank imports, payment reconciliation.

Revision ID: 008_bank_imports
Revises: 007_ledger
Create Date: 2026-09-01

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "008_bank_imports"
down_revision: Union[str, Sequence[str], None] = "007_ledger"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "bank_imports",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("line_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_bank_imports"),
    )

    op.create_table(
        "bank_import_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("import_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("description", sa.String(length=512), nullable=False),
        sa.Column("reference", sa.String(length=128), nullable=True),
        sa.Column("amount_zar", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("matched_payment_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["import_id"],
            ["bank_imports.id"],
            name="fk_bank_import_lines_import_id_bank_imports",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["matched_payment_id"],
            ["payments.id"],
            name="fk_bank_import_lines_matched_payment_id_payments",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_bank_import_lines"),
    )
    op.create_index("ix_bank_import_lines_import_id", "bank_import_lines", ["import_id"])
    op.create_index(
        "ix_bank_import_lines_matched_payment_id",
        "bank_import_lines",
        ["matched_payment_id"],
    )

    op.add_column(
        "payments",
        sa.Column(
            "is_reconciled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "payments",
        sa.Column("reconciled_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("payments", "reconciled_at")
    op.drop_column("payments", "is_reconciled")
    op.drop_index("ix_bank_import_lines_matched_payment_id", table_name="bank_import_lines")
    op.drop_index("ix_bank_import_lines_import_id", table_name="bank_import_lines")
    op.drop_table("bank_import_lines")
    op.drop_table("bank_imports")
