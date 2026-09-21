"""Company settings wave 2: logo, till discount cap, PO threshold, books periods.

Revision ID: 043_company_settings_wave2
Revises: 042_company_settings
Create Date: 2026-09-13

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "043_company_settings_wave2"
down_revision: Union[str, Sequence[str], None] = "042_company_settings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("team_settings", sa.Column("logo_storage_key", sa.Text(), nullable=True))
    op.add_column(
        "team_settings",
        sa.Column("max_till_discount_percent", sa.Numeric(5, 2), nullable=True),
    )
    op.add_column(
        "team_settings",
        sa.Column("po_approval_threshold_zar", sa.Numeric(14, 2), nullable=True),
    )

    op.create_table(
        "books_periods",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("period_from", sa.Date(), nullable=False),
        sa.Column("period_to", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="open"),
        sa.Column("locked_at", sa.DateTime(), nullable=True),
        sa.Column("locked_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reopen_reason", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["locked_by_user_id"],
            ["users.id"],
            name="fk_books_periods_locked_by_user_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_books_periods"),
        sa.UniqueConstraint(
            "period_from",
            "period_to",
            name="uq_books_periods_period_from_period_to",
        ),
        sa.CheckConstraint(
            "status IN ('open', 'locked')",
            name="ck_books_periods_status",
        ),
        sa.CheckConstraint(
            "period_from <= period_to",
            name="ck_books_periods_period_range",
        ),
    )
    op.create_index(
        "ix_books_periods_locked_by_user_id",
        "books_periods",
        ["locked_by_user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_books_periods_locked_by_user_id", table_name="books_periods")
    op.drop_table("books_periods")

    op.drop_column("team_settings", "po_approval_threshold_zar")
    op.drop_column("team_settings", "max_till_discount_percent")
    op.drop_column("team_settings", "logo_storage_key")
