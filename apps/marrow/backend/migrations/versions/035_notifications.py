"""notifications

Revision ID: 035
Revises: 034
Create Date: 2026-07-12 00:00:00.000000

Notifications table + create_notification SECURITY DEFINER function (#304).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.sql.social_functions import CREATE_NOTIFICATION_SQL, SOCIAL_NOTIFIER_POLICY_SQL

revision: str = "035"
down_revision: Union[str, None] = "034"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notifications",
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
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column(
            "payload", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(now() at time zone 'utc')"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index(
        "ix_notifications_user_unread",
        "notifications",
        ["user_id"],
        postgresql_where=sa.text("read_at IS NULL"),
    )

    bind = op.get_bind()
    bind.execute(sa.text("ALTER TABLE notifications ENABLE ROW LEVEL SECURITY"))
    bind.execute(sa.text("ALTER TABLE notifications FORCE ROW LEVEL SECURITY"))
    bind.execute(
        sa.text(
            """
            CREATE POLICY notifications_owner ON notifications
                FOR ALL
                USING (user_id = current_setting('app.user_id', true)::uuid)
                WITH CHECK (user_id = current_setting('app.user_id', true)::uuid)
            """
        )
    )
    bind.execute(sa.text(SOCIAL_NOTIFIER_POLICY_SQL))
    bind.execute(sa.text(CREATE_NOTIFICATION_SQL))


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DROP FUNCTION IF EXISTS create_notification(uuid, text, jsonb)"))
    bind.execute(sa.text("DROP POLICY IF EXISTS social_notifier ON notifications"))
    bind.execute(sa.text("DROP POLICY IF EXISTS notifications_owner ON notifications"))
    bind.execute(sa.text("ALTER TABLE notifications NO FORCE ROW LEVEL SECURITY"))
    bind.execute(sa.text("ALTER TABLE notifications DISABLE ROW LEVEL SECURITY"))
    op.drop_index("ix_notifications_user_unread", table_name="notifications")
    op.drop_index("ix_notifications_user_id", table_name="notifications")
    op.drop_table("notifications")
