"""Manual journals: status, entry_date, source, journal_number, voided_by.

Revision ID: 022_manual_journals
Revises: 021_v2_till_eft_tender
Create Date: 2026-09-01

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "022_manual_journals"
down_revision: Union[str, Sequence[str], None] = "021_v2_till_eft_tender"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "journal_entries",
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="posted",
        ),
    )
    op.add_column(
        "journal_entries",
        sa.Column(
            "entry_date",
            sa.Date(),
            nullable=False,
            server_default=sa.text("CURRENT_DATE"),
        ),
    )
    op.execute(sa.text("UPDATE journal_entries SET entry_date = created_at::date"))
    op.add_column(
        "journal_entries",
        sa.Column("source", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "journal_entries",
        sa.Column("journal_number", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "journal_entries",
        sa.Column("voided_by_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_journal_entries_voided_by_id_journal_entries",
        "journal_entries",
        "journal_entries",
        ["voided_by_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_unique_constraint(
        "uq_journal_entries_journal_number",
        "journal_entries",
        ["journal_number"],
    )
    op.create_check_constraint(
        "ck_journal_entries_status",
        "journal_entries",
        "status IN ('draft', 'posted', 'voided')",
    )
    op.drop_constraint("ck_journal_entries_document_type", "journal_entries", type_="check")
    op.create_check_constraint(
        "ck_journal_entries_document_type",
        "journal_entries",
        "document_type IN ("
        "'invoice', 'credit_note', 'bill', 'payment', 'stock_adjustment', 'manual'"
        ")",
    )


def downgrade() -> None:
    op.drop_constraint("ck_journal_entries_document_type", "journal_entries", type_="check")
    op.create_check_constraint(
        "ck_journal_entries_document_type",
        "journal_entries",
        "document_type IN ('invoice', 'credit_note', 'bill', 'payment', 'stock_adjustment')",
    )
    op.drop_constraint("ck_journal_entries_status", "journal_entries", type_="check")
    op.drop_constraint("uq_journal_entries_journal_number", "journal_entries", type_="unique")
    op.drop_constraint(
        "fk_journal_entries_voided_by_id_journal_entries",
        "journal_entries",
        type_="foreignkey",
    )
    op.drop_column("journal_entries", "voided_by_id")
    op.drop_column("journal_entries", "journal_number")
    op.drop_column("journal_entries", "source")
    op.drop_column("journal_entries", "entry_date")
    op.drop_column("journal_entries", "status")
