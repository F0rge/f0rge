"""B5 bank rules for CSV recon coding.

Revision ID: 026_bank_rules
Revises: 025_vat201_periods
Create Date: 2026-09-01

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "026_bank_rules"
down_revision: Union[str, Sequence[str], None] = "025_vat201_periods"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "bank_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bank_account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pattern", sa.String(length=128), nullable=False),
        sa.Column("target_account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["bank_account_id"],
            ["accounts.id"],
            name="fk_bank_rules_bank_account_id_accounts",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["target_account_id"],
            ["accounts.id"],
            name="fk_bank_rules_target_account_id_accounts",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_bank_rules"),
        sa.UniqueConstraint(
            "bank_account_id",
            "pattern",
            name="uq_bank_rules_bank_account_id_pattern",
        ),
    )
    op.create_index("ix_bank_rules_bank_account_id", "bank_rules", ["bank_account_id"])
    op.create_index("ix_bank_rules_target_account_id", "bank_rules", ["target_account_id"])


def downgrade() -> None:
    op.drop_index("ix_bank_rules_target_account_id", table_name="bank_rules")
    op.drop_index("ix_bank_rules_bank_account_id", table_name="bank_rules")
    op.drop_table("bank_rules")
