"""connections

Revision ID: 036
Revises: 035
Create Date: 2026-07-12 00:00:00.000000

Connections table with split RLS policies (#305).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "036"
down_revision: Union[str, None] = "035"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None

_CONNECTIONS_RLS = [
    "ALTER TABLE connections ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE connections FORCE ROW LEVEL SECURITY",
    """
    CREATE POLICY connections_select ON connections FOR SELECT
        USING (current_setting('app.user_id', true)::uuid IN (user_low, user_high))
    """,
    """
    CREATE POLICY connections_insert ON connections FOR INSERT
        WITH CHECK (
            requester_id = current_setting('app.user_id', true)::uuid
            AND current_setting('app.user_id', true)::uuid IN (user_low, user_high)
        )
    """,
    """
    CREATE POLICY connections_update ON connections FOR UPDATE
        USING (current_setting('app.user_id', true)::uuid IN (user_low, user_high))
        WITH CHECK (current_setting('app.user_id', true)::uuid IN (user_low, user_high))
    """,
    """
    CREATE POLICY connections_delete ON connections FOR DELETE
        USING (current_setting('app.user_id', true)::uuid IN (user_low, user_high))
    """,
]


def upgrade() -> None:
    op.create_table(
        "connections",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "user_low",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_high",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "requester_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.Text(), server_default="pending", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(now() at time zone 'utc')"),
            nullable=False,
        ),
        sa.Column("responded_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("user_low < user_high", name="ck_connections_order"),
        sa.CheckConstraint("status IN ('pending', 'accepted')", name="ck_connections_status"),
        sa.CheckConstraint("requester_id IN (user_low, user_high)", name="ck_connections_party"),
        sa.UniqueConstraint("user_low", "user_high", name="uq_connections_pair"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_connections_user_low", "connections", ["user_low"])
    op.create_index("ix_connections_user_high", "connections", ["user_high"])

    bind = op.get_bind()
    for stmt in _CONNECTIONS_RLS:
        bind.execute(sa.text(stmt))


def downgrade() -> None:
    bind = op.get_bind()
    for policy in (
        "connections_delete",
        "connections_update",
        "connections_insert",
        "connections_select",
    ):
        bind.execute(sa.text(f"DROP POLICY IF EXISTS {policy} ON connections"))
    bind.execute(sa.text("ALTER TABLE connections NO FORCE ROW LEVEL SECURITY"))
    bind.execute(sa.text("ALTER TABLE connections DISABLE ROW LEVEL SECURITY"))
    op.drop_index("ix_connections_user_high", table_name="connections")
    op.drop_index("ix_connections_user_low", table_name="connections")
    op.drop_table("connections")
