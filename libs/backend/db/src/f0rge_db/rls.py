from __future__ import annotations

from typing import Iterable

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncConnection


async def enable_tenant_isolation(conn: AsyncConnection, tables: Iterable[str]) -> None:
    """Enable FORCE RLS + a per-user ``tenant_isolation`` policy on each table.

    Each table must have a ``user_id`` column; the policy compares it against
    the ``app.user_id`` GUC set by ``f0rge_db.tenant.apply_session_user_id``.
    """
    for table in tables:
        await conn.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
        await conn.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
        await conn.execute(
            sa.text(
                f"""
                CREATE POLICY tenant_isolation ON {table}
                    FOR ALL
                    USING (user_id = current_setting('app.user_id', true)::uuid)
                    WITH CHECK (user_id = current_setting('app.user_id', true)::uuid)
                """
            )
        )


async def create_service_role_policy(
    conn: AsyncConnection,
    *,
    name: str,
    tables: Iterable[str],
    role: str,
    command: str = "ALL",
) -> None:
    """Create policy ``name`` on each table gating on ``app.service_role = role``.

    ``command="ALL"`` emits USING + WITH CHECK (read/write paths, e.g. a
    provisioner or worker); ``command="SELECT"`` emits USING only (read-only
    lookups, e.g. MCP auth). Postgres rejects WITH CHECK on SELECT policies.
    """
    condition = f"current_setting('app.service_role', true) = '{role}'"
    with_check = f"\n                    WITH CHECK ({condition})" if command == "ALL" else ""
    for table in tables:
        await conn.execute(
            sa.text(
                f"""
                CREATE POLICY {name} ON {table}
                    FOR {command}
                    USING ({condition}){with_check}
                """
            )
        )
