"""VAT201 bi-monthly periods, lock snapshot, reopen events.

Revision ID: 025_vat201_periods
Revises: 024_bank_accounts
Create Date: 2026-09-01

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "025_vat201_periods"
down_revision: Union[str, Sequence[str], None] = "024_bank_accounts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "vat201_periods",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("period_from", sa.Date(), nullable=False),
        sa.Column("period_to", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column(
            "snapshot_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("locked_at", sa.DateTime(), nullable=True),
        sa.Column("locked_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reopen_reason", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["locked_by_user_id"],
            ["users.id"],
            name="fk_vat201_periods_locked_by_user_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_vat201_periods"),
        sa.UniqueConstraint(
            "period_from",
            "period_to",
            name="uq_vat201_periods_period_from_period_to",
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'due', 'locked')",
            name="ck_vat201_periods_status",
        ),
    )
    op.create_index(
        "ix_vat201_periods_locked_by_user_id",
        "vat201_periods",
        ["locked_by_user_id"],
    )

    op.create_table(
        "vat201_period_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("period_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column(
            "snapshot_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reason", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["period_id"],
            ["vat201_periods.id"],
            name="fk_vat201_period_events_period_id_vat201_periods",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name="fk_vat201_period_events_actor_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_vat201_period_events"),
        sa.CheckConstraint(
            "action IN ('lock', 'reopen')",
            name="ck_vat201_period_events_action",
        ),
    )
    op.create_index(
        "ix_vat201_period_events_period_id",
        "vat201_period_events",
        ["period_id"],
    )
    op.create_index(
        "ix_vat201_period_events_actor_user_id",
        "vat201_period_events",
        ["actor_user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_vat201_period_events_actor_user_id", table_name="vat201_period_events")
    op.drop_index("ix_vat201_period_events_period_id", table_name="vat201_period_events")
    op.drop_table("vat201_period_events")
    op.drop_index("ix_vat201_periods_locked_by_user_id", table_name="vat201_periods")
    op.drop_table("vat201_periods")
