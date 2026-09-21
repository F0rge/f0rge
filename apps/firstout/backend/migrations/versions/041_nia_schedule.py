"""Nia scheduled tasks and run log.

Revision ID: 041_nia_schedule
Revises: 040_nia_audit
Create Date: 2026-09-02

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "041_nia_schedule"
down_revision: Union[str, Sequence[str], None] = "040_nia_audit"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "nia_scheduled_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("team_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("timezone", sa.Text(), nullable=False),
        sa.Column("cadence", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("notify_only_if_changed", sa.Boolean(), nullable=False),
        sa.Column("last_run_at", sa.DateTime(), nullable=True),
        sa.Column("last_status", sa.Text(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("last_output_hash", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["team_id"],
            ["teams.id"],
            name="fk_nia_scheduled_tasks_team_id_teams",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_nia_scheduled_tasks_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_nia_scheduled_tasks"),
        sa.CheckConstraint(
            "last_status IS NULL OR last_status IN ('ok', 'skipped', 'error', 'needs_ok')",
            name="ck_nia_scheduled_tasks_last_status",
        ),
    )
    op.create_index("ix_nia_scheduled_tasks_user_id", "nia_scheduled_tasks", ["user_id"])
    op.create_index("ix_nia_scheduled_tasks_team_id", "nia_scheduled_tasks", ["team_id"])
    op.create_index(
        "ix_nia_scheduled_tasks_enabled",
        "nia_scheduled_tasks",
        ["enabled"],
    )

    op.create_table(
        "nia_scheduled_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("thread_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["nia_scheduled_tasks.id"],
            name="fk_nia_scheduled_runs_task_id_nia_scheduled_tasks",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["thread_id"],
            ["nia_threads.id"],
            name="fk_nia_scheduled_runs_thread_id_nia_threads",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_nia_scheduled_runs"),
        sa.CheckConstraint(
            "status IN ('ok', 'skipped', 'error', 'needs_ok')",
            name="ck_nia_scheduled_runs_status",
        ),
    )
    op.create_index("ix_nia_scheduled_runs_task_id", "nia_scheduled_runs", ["task_id"])
    op.create_index("ix_nia_scheduled_runs_thread_id", "nia_scheduled_runs", ["thread_id"])


def downgrade() -> None:
    op.drop_index("ix_nia_scheduled_runs_thread_id", table_name="nia_scheduled_runs")
    op.drop_index("ix_nia_scheduled_runs_task_id", table_name="nia_scheduled_runs")
    op.drop_table("nia_scheduled_runs")
    op.drop_index("ix_nia_scheduled_tasks_enabled", table_name="nia_scheduled_tasks")
    op.drop_index("ix_nia_scheduled_tasks_team_id", table_name="nia_scheduled_tasks")
    op.drop_index("ix_nia_scheduled_tasks_user_id", table_name="nia_scheduled_tasks")
    op.drop_table("nia_scheduled_tasks")
