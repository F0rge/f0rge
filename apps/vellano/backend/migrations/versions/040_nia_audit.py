"""Nia HITL audit events.

Revision ID: 040_nia_audit
Revises: 039_nia_caps
Create Date: 2026-09-02

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "040_nia_audit"
down_revision: Union[str, Sequence[str], None] = "039_nia_caps"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "nia_audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("thread_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("tool_name", sa.Text(), nullable=False),
        sa.Column(
            "args",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("decision", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=True),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["thread_id"],
            ["nia_threads.id"],
            name="fk_nia_audit_events_thread_id_nia_threads",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_nia_audit_events_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_nia_audit_events"),
        sa.CheckConstraint(
            "decision IN ('accept', 'decline', 'cancel')",
            name="ck_nia_audit_events_decision",
        ),
    )
    op.create_index("ix_nia_audit_events_user_id", "nia_audit_events", ["user_id"])
    op.create_index("ix_nia_audit_events_thread_id", "nia_audit_events", ["thread_id"])


def downgrade() -> None:
    op.drop_index("ix_nia_audit_events_thread_id", table_name="nia_audit_events")
    op.drop_index("ix_nia_audit_events_user_id", table_name="nia_audit_events")
    op.drop_table("nia_audit_events")
