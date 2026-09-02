"""Nia threads, messages, and usage ledger.

Revision ID: 037_nia_threads
Revises: 036_picks
Create Date: 2026-09-02

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "037_nia_threads"
down_revision: Union[str, Sequence[str], None] = "036_picks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "nia_threads",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("team_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("archived_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["team_id"],
            ["teams.id"],
            name="fk_nia_threads_team_id_teams",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_nia_threads_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_nia_threads"),
    )
    op.create_index("ix_nia_threads_user_id", "nia_threads", ["user_id"])
    op.create_index("ix_nia_threads_team_id", "nia_threads", ["team_id"])

    op.create_table(
        "nia_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("thread_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "structured_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["thread_id"],
            ["nia_threads.id"],
            name="fk_nia_messages_thread_id_nia_threads",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_nia_messages"),
        sa.CheckConstraint(
            "role IN ('user', 'assistant', 'system', 'tool')",
            name="ck_nia_messages_role",
        ),
    )
    op.create_index("ix_nia_messages_thread_id", "nia_messages", ["thread_id"])

    op.create_table(
        "nia_usage_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("thread_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False),
        sa.Column("completion_tokens", sa.Integer(), nullable=False),
        sa.Column("total_tokens", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("openrouter_generation_id", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["thread_id"],
            ["nia_threads.id"],
            name="fk_nia_usage_events_thread_id_nia_threads",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_nia_usage_events_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_nia_usage_events"),
    )
    op.create_index("ix_nia_usage_events_user_id", "nia_usage_events", ["user_id"])
    op.create_index("ix_nia_usage_events_thread_id", "nia_usage_events", ["thread_id"])


def downgrade() -> None:
    op.drop_index("ix_nia_usage_events_thread_id", table_name="nia_usage_events")
    op.drop_index("ix_nia_usage_events_user_id", table_name="nia_usage_events")
    op.drop_table("nia_usage_events")

    op.drop_index("ix_nia_messages_thread_id", table_name="nia_messages")
    op.drop_table("nia_messages")

    op.drop_index("ix_nia_threads_team_id", table_name="nia_threads")
    op.drop_index("ix_nia_threads_user_id", table_name="nia_threads")
    op.drop_table("nia_threads")
