"""external_api_tokens

Revision ID: 057
Revises: 056
Create Date: 2026-10-03 00:00:00.000000

Multiple live MCP bearer tokens per user. Copies each existing
``user_settings.external_api_token_hash`` into the new table and leaves that
column untouched, so the token already in the field keeps authenticating.
The legacy columns stay until reads use this table.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from f0rge_db.rls import create_service_role_policy_sync, migration_bypass

revision: str = "057"
down_revision: Union[str, None] = "056"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None

# Same string as app.models.external_api_token.LEGACY_EXTERNAL_API_TOKEN_NAME.
# Kept literal so this migration does not import the app.
_LEGACY_NAME = "existing token"

COPY_EXISTING_TOKEN_HASHES_SQL = sa.text(
    """
    INSERT INTO external_api_tokens (user_id, token_hash, name, created_at)
    SELECT user_id, external_api_token_hash, :name, NULL
    FROM user_settings
    WHERE external_api_token_hash IS NOT NULL
    ON CONFLICT ON CONSTRAINT uq_external_api_tokens_token_hash DO NOTHING
    """
)


def copy_existing_external_api_token_hashes(bind: sa.Connection) -> None:
    """Insert current hashes. Does not UPDATE user_settings."""
    bind.execute(COPY_EXISTING_TOKEN_HASHES_SQL, {"name": _LEGACY_NAME})


def _role_exists(bind: sa.Connection, role: str) -> bool:
    return bool(
        bind.execute(
            sa.text("SELECT 1 FROM pg_roles WHERE rolname = :role"),
            {"role": role},
        ).scalar_one_or_none()
    )


def upgrade() -> None:
    op.create_table(
        "external_api_tokens",
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
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_external_api_tokens_token_hash"),
    )
    op.create_index("ix_external_api_tokens_user_id", "external_api_tokens", ["user_id"])

    bind = op.get_bind()
    bind.execute(sa.text("ALTER TABLE external_api_tokens ENABLE ROW LEVEL SECURITY"))
    bind.execute(sa.text("ALTER TABLE external_api_tokens FORCE ROW LEVEL SECURITY"))
    bind.execute(
        sa.text(
            """
            CREATE POLICY tenant_isolation ON external_api_tokens
                FOR ALL
                USING (user_id = current_setting('app.user_id', true)::uuid)
                WITH CHECK (user_id = current_setting('app.user_id', true)::uuid)
            """
        )
    )
    create_service_role_policy_sync(
        bind,
        name="mcp_auth_lookup",
        tables=("external_api_tokens",),
        role="mcp_auth",
        command="SELECT",
    )

    if _role_exists(bind, "healthtracker_app"):
        bind.execute(
            sa.text(
                "GRANT SELECT, INSERT, UPDATE, DELETE ON external_api_tokens TO healthtracker_app"
            )
        )
    if _role_exists(bind, "healthtracker_ro"):
        bind.execute(sa.text("GRANT SELECT ON external_api_tokens TO healthtracker_ro"))

    # Cross-tenant copy. The hash column is only read — never written.
    with migration_bypass(bind, ("user_settings", "external_api_tokens")):
        copy_existing_external_api_token_hashes(bind)


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DROP POLICY IF EXISTS mcp_auth_lookup ON external_api_tokens"))
    bind.execute(sa.text("DROP POLICY IF EXISTS tenant_isolation ON external_api_tokens"))
    bind.execute(sa.text("ALTER TABLE external_api_tokens NO FORCE ROW LEVEL SECURITY"))
    bind.execute(sa.text("ALTER TABLE external_api_tokens DISABLE ROW LEVEL SECURITY"))
    op.drop_index("ix_external_api_tokens_user_id", table_name="external_api_tokens")
    op.drop_table("external_api_tokens")
