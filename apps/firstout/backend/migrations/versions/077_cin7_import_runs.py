"""Audit log for admin Cin7 import jobs.

Revision ID: 077_cin7_import_runs
Revises: 076_sku_price_tiers

One row per dry run or commit: who ran it, when, the file hash, the mode,
the status, and the summary. A unique index on active_lock allows a single
in-flight job. Uploads are private storage keys, not public URLs.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "077_cin7_import_runs"
down_revision: Union[str, Sequence[str], None] = "076_sku_price_tiers"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cin7_import_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_email", sa.String(length=255), nullable=False),
        sa.Column("file_sha256", sa.String(length=64), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=True),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("dry_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column(
            "summary",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "warnings",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "errors",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("warning_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "barcode_replacements",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("active_lock", sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(["dry_run_id"], ["cin7_import_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "mode IN ('dry_run', 'commit')",
            name="ck_cin7_import_runs_mode",
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed')",
            name="ck_cin7_import_runs_status",
        ),
    )
    op.create_index("ix_cin7_import_runs_created_at", "cin7_import_runs", ["created_at"])
    op.create_index("ix_cin7_import_runs_file_sha256", "cin7_import_runs", ["file_sha256"])
    op.create_index("ix_cin7_import_runs_user_id", "cin7_import_runs", ["user_id"])
    op.create_index("ix_cin7_import_runs_dry_run_id", "cin7_import_runs", ["dry_run_id"])
    op.create_index(
        "uq_cin7_import_runs_one_active",
        "cin7_import_runs",
        ["active_lock"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_cin7_import_runs_one_active", table_name="cin7_import_runs")
    op.drop_index("ix_cin7_import_runs_dry_run_id", table_name="cin7_import_runs")
    op.drop_index("ix_cin7_import_runs_user_id", table_name="cin7_import_runs")
    op.drop_index("ix_cin7_import_runs_file_sha256", table_name="cin7_import_runs")
    op.drop_index("ix_cin7_import_runs_created_at", table_name="cin7_import_runs")
    op.drop_table("cin7_import_runs")
