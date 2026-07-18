"""device_tokens

Revision ID: 046
Revises: 045
Create Date: 2026-07-18 00:00:00.000000

APNs device token registry (#391). Tenant-isolated like every user-owned
table, plus a ``device_registrar`` service-role policy so registration can
delete a token row left behind by another user (phone changed hands) that
RLS would otherwise hide.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from f0rge_db.rls import create_service_role_policy_sync

revision: str = "046"
down_revision: Union[str, None] = "045"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "device_tokens",
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
        sa.Column("token", sa.Text(), nullable=False),
        sa.Column("platform", sa.Text(), server_default="ios", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(now() at time zone 'utc')"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token", name="uq_device_tokens_token"),
    )
    op.create_index("ix_device_tokens_user_id", "device_tokens", ["user_id"])

    bind = op.get_bind()
    bind.execute(sa.text("ALTER TABLE device_tokens ENABLE ROW LEVEL SECURITY"))
    bind.execute(sa.text("ALTER TABLE device_tokens FORCE ROW LEVEL SECURITY"))
    # Same policy name/shape f0rge_db.rls.enable_tenant_isolation emits for
    # every USER_OWNED_TABLES entry (test bootstrap parity).
    bind.execute(
        sa.text(
            """
            CREATE POLICY tenant_isolation ON device_tokens
                FOR ALL
                USING (user_id = current_setting('app.user_id', true)::uuid)
                WITH CHECK (user_id = current_setting('app.user_id', true)::uuid)
            """
        )
    )
    create_service_role_policy_sync(
        bind,
        name="device_registrar",
        tables=("device_tokens",),
        role="device_registrar",
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DROP POLICY IF EXISTS device_registrar ON device_tokens"))
    bind.execute(sa.text("DROP POLICY IF EXISTS tenant_isolation ON device_tokens"))
    bind.execute(sa.text("ALTER TABLE device_tokens NO FORCE ROW LEVEL SECURITY"))
    bind.execute(sa.text("ALTER TABLE device_tokens DISABLE ROW LEVEL SECURITY"))
    op.drop_index("ix_device_tokens_user_id", table_name="device_tokens")
    op.drop_table("device_tokens")
