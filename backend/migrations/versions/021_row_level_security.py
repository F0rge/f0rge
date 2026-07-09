"""row_level_security

Revision ID: 021
Revises: 020
Create Date: 2026-07-09 12:00:00.000000

Enable FORCE ROW LEVEL SECURITY on every user-owned table with tenant
isolation policies keyed on ``current_setting('app.user_id', true)::uuid``.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.rls import USER_OWNED_TABLES

revision: str = "021"
down_revision: Union[str, None] = "020"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    for table in USER_OWNED_TABLES:
        bind.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
        bind.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
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
    bind.execute(
        sa.text(
            """
            CREATE POLICY mcp_auth_lookup ON user_settings
                FOR SELECT
                USING (current_setting('app.service_role', true) = 'mcp_auth')
            """
        )
    )
    bind.execute(
        sa.text(
            """
            CREATE POLICY worker_queue ON embedding_queue
                FOR ALL
                USING (current_setting('app.service_role', true) = 'worker')
                WITH CHECK (current_setting('app.service_role', true) = 'worker')
            """
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DROP POLICY IF EXISTS worker_queue ON embedding_queue"))
    bind.execute(sa.text("DROP POLICY IF EXISTS mcp_auth_lookup ON user_settings"))
    for table in reversed(USER_OWNED_TABLES):
        bind.execute(sa.text(f"DROP POLICY IF EXISTS tenant_isolation ON {table}"))
        bind.execute(sa.text(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY"))
        bind.execute(sa.text(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY"))
