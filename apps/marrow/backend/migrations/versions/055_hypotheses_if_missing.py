"""Ensure hypotheses tables exist (production repair)

Revision ID: 055
Revises: 054
Create Date: 2026-09-29 14:20:00.000000

Idempotent guard for environments where alembic_version reached 054 but
revision 053 objects were never created on the runtime database (e.g.
migrations ran against a different DATABASE_URL than the app/MCP runtime).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "055"
down_revision: Union[str, None] = "054"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None

_TABLES = ("hypotheses", "n_of_1_slots")


def _role_exists(bind: sa.Connection, role: str) -> bool:
    return bool(
        bind.execute(
            sa.text("SELECT 1 FROM pg_roles WHERE rolname = :role"),
            {"role": role},
        ).scalar_one_or_none()
    )


def _table_exists(bind: sa.Connection, table: str) -> bool:
    return bool(
        bind.execute(
            sa.text(
                """
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = :table
                """
            ),
            {"table": table},
        ).scalar_one_or_none()
    )


def _policy_exists(bind: sa.Connection, table: str) -> bool:
    return bool(
        bind.execute(
            sa.text(
                """
                SELECT 1 FROM pg_policies
                WHERE schemaname = 'public' AND tablename = :table AND policyname = 'tenant_isolation'
                """
            ),
            {"table": table},
        ).scalar_one_or_none()
    )


def _enable_tenant_rls(bind: sa.Connection, table: str) -> None:
    bind.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
    bind.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
    if not _policy_exists(bind, table):
        bind.execute(
            sa.text(
                f"""
                CREATE POLICY tenant_isolation ON {table}
                    FOR ALL
                    USING (user_id = current_setting('app.user_id', true)::uuid)
                    WITH CHECK (user_id = current_setting('app.user_id', true)::uuid)
                """
            )
        )


def upgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind, "hypotheses"):
        op.create_table(
            "hypotheses",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                server_default=sa.text("gen_random_uuid()"),
                nullable=False,
            ),
            sa.Column(
                "user_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("slug", sa.String(length=64), nullable=False),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("status", sa.String(length=16), nullable=False),
            sa.Column("layer", sa.Integer(), nullable=True),
            sa.Column("kill_test", sa.Text(), nullable=True),
            sa.Column("next_move", sa.Text(), nullable=True),
            sa.Column("last_evidence", sa.Text(), nullable=True),
            sa.Column("cite", sa.Text(), nullable=True),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column(
                "created_at",
                sa.DateTime(),
                server_default=sa.text("(now() at time zone 'utc')"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                server_default=sa.text("(now() at time zone 'utc')"),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", "slug", name="uq_hypotheses_user_id_slug"),
            sa.CheckConstraint(
                "status IN ('live', 'weakening', 'killed', 'parked')",
                name="ck_hypotheses_status",
            ),
            sa.CheckConstraint("layer IS NULL OR layer IN (1, 2)", name="ck_hypotheses_layer"),
        )
        op.create_index("ix_hypotheses_user_id", "hypotheses", ["user_id"])
        op.create_index("ix_hypotheses_user_id_status", "hypotheses", ["user_id", "status"])
        op.create_index(
            "ix_hypotheses_user_id_sort_order",
            "hypotheses",
            ["user_id", "sort_order"],
        )

    if not _table_exists(bind, "n_of_1_slots"):
        op.create_table(
            "n_of_1_slots",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                server_default=sa.text("gen_random_uuid()"),
                nullable=False,
            ),
            sa.Column(
                "user_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("change", sa.Text(), nullable=False),
            sa.Column("start", sa.Date(), nullable=False),
            sa.Column("watch_field", sa.Text(), nullable=False),
            sa.Column("stop_rule", sa.Text(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(),
                server_default=sa.text("(now() at time zone 'utc')"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                server_default=sa.text("(now() at time zone 'utc')"),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", name="uq_n_of_1_slots_user_id"),
        )
        op.create_index("ix_n_of_1_slots_user_id", "n_of_1_slots", ["user_id"])

    for table in _TABLES:
        if _table_exists(bind, table):
            _enable_tenant_rls(bind, table)

    if _role_exists(bind, "healthtracker_app"):
        bind.execute(
            sa.text(
                "GRANT SELECT, INSERT, UPDATE, DELETE ON hypotheses, n_of_1_slots "
                "TO healthtracker_app"
            )
        )
    if _role_exists(bind, "healthtracker_ro"):
        bind.execute(sa.text("GRANT SELECT ON hypotheses, n_of_1_slots TO healthtracker_ro"))


def downgrade() -> None:
    # No-op: do not drop hypotheses data on downgrade from a repair revision.
    pass
