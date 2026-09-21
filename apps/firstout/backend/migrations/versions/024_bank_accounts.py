"""B2 bank recon accounts, import account_id, journal match.

Revision ID: 024_bank_accounts
Revises: 023_category_coa
Create Date: 2026-09-01

"""

from __future__ import annotations

import datetime
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "024_bank_accounts"
down_revision: Union[str, Sequence[str], None] = "023_category_coa"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

BANK_ACCOUNTS = (
    ("1110", "Credit card"),
    ("1120", "Petty cash"),
    ("1130", "Inventory clearing"),
    ("1140", "Supplier clearing"),
)


def upgrade() -> None:
    op.add_column(
        "accounts",
        sa.Column(
            "is_bank",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.execute(sa.text("UPDATE accounts SET is_bank = true WHERE code = '1100'"))

    conn = op.get_bind()
    now = datetime.datetime.utcnow()
    existing_codes = {
        row[0] for row in conn.execute(sa.text("SELECT code FROM accounts")).fetchall()
    }
    accounts = sa.table(
        "accounts",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("type", sa.String),
        sa.column("is_system", sa.Boolean),
        sa.column("is_archived", sa.Boolean),
        sa.column("is_bank", sa.Boolean),
        sa.column("tax_treatment", sa.String),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )
    to_insert = [
        {
            "id": uuid.uuid4(),
            "code": code,
            "name": name,
            "type": "asset",
            "is_system": True,
            "is_archived": False,
            "is_bank": True,
            "tax_treatment": "none",
            "created_at": now,
            "updated_at": now,
        }
        for code, name in BANK_ACCOUNTS
        if code not in existing_codes
    ]
    if to_insert:
        op.bulk_insert(accounts, to_insert)

    op.add_column(
        "bank_imports",
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE bank_imports SET account_id = (SELECT id FROM accounts WHERE code = '1100')"
        )
    )
    op.alter_column("bank_imports", "account_id", nullable=False)
    op.create_foreign_key(
        "fk_bank_imports_account_id_accounts",
        "bank_imports",
        "accounts",
        ["account_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_bank_imports_account_id", "bank_imports", ["account_id"])

    op.add_column(
        "bank_import_lines",
        sa.Column("matched_journal_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_bank_import_lines_matched_journal_id_journal_entries",
        "bank_import_lines",
        "journal_entries",
        ["matched_journal_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_bank_import_lines_matched_journal_id",
        "bank_import_lines",
        ["matched_journal_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_bank_import_lines_matched_journal_id", table_name="bank_import_lines")
    op.drop_constraint(
        "fk_bank_import_lines_matched_journal_id_journal_entries",
        "bank_import_lines",
        type_="foreignkey",
    )
    op.drop_column("bank_import_lines", "matched_journal_id")
    op.drop_index("ix_bank_imports_account_id", table_name="bank_imports")
    op.drop_constraint("fk_bank_imports_account_id_accounts", "bank_imports", type_="foreignkey")
    op.drop_column("bank_imports", "account_id")
    op.drop_column("accounts", "is_bank")
