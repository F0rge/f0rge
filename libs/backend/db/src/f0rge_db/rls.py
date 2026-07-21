from __future__ import annotations

from contextlib import contextmanager
from typing import Generator, Iterable

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncConnection

MIGRATION_SERVICE_ROLE = "migrator"
DEFAULT_MIGRATION_POLICY = "migration_bypass"
# Nil UUID sentinel so ``tenant_isolation``'s ``app.user_id::uuid`` cast never
# errors on ``''``. Used by migration_bypass and ``apply_service_role``.
MIGRATION_DUMMY_USER_ID = "00000000-0000-0000-0000-000000000000"


def _service_role_policy_sql(
    *,
    name: str,
    table: str,
    role: str,
    command: str = "ALL",
) -> sa.TextClause:
    condition = f"current_setting('app.service_role', true) = '{role}'"
    with_check = f"\n                    WITH CHECK ({condition})" if command == "ALL" else ""
    return sa.text(
        f"""
        CREATE POLICY {name} ON {table}
            FOR {command}
            USING ({condition}){with_check}
        """
    )


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
    for table in tables:
        await conn.execute(
            _service_role_policy_sql(name=name, table=table, role=role, command=command)
        )


def create_service_role_policy_sync(
    conn: sa.Connection,
    *,
    name: str,
    tables: Iterable[str],
    role: str,
    command: str = "ALL",
) -> None:
    """Sync variant of :func:`create_service_role_policy` for Alembic migrations."""
    for table in tables:
        conn.execute(_service_role_policy_sql(name=name, table=table, role=role, command=command))


def install_migration_bypass(
    conn: sa.Connection,
    tables: Iterable[str],
    *,
    name: str = DEFAULT_MIGRATION_POLICY,
) -> None:
    """Create a transient ``migration_bypass`` policy for cross-tenant migration writes."""
    create_service_role_policy_sync(
        conn,
        name=name,
        tables=tables,
        role=MIGRATION_SERVICE_ROLE,
    )
    # Nil UUID sentinel: ``tenant_isolation`` casts ``app.user_id`` to uuid; an unset
    # GUC is ``''`` and raises. The sentinel evaluates false for real rows while
    # ``migration_bypass`` authorizes the cross-tenant work.
    conn.execute(
        sa.text("SELECT set_config('app.user_id', :user_id, true)"),
        {"user_id": MIGRATION_DUMMY_USER_ID},
    )
    conn.execute(
        sa.text("SELECT set_config('app.service_role', :role, true)"),
        {"role": MIGRATION_SERVICE_ROLE},
    )


def remove_migration_bypass(
    conn: sa.Connection,
    tables: Iterable[str],
    *,
    name: str = DEFAULT_MIGRATION_POLICY,
) -> None:
    """Drop the transient migration policy and clear migration GUCs."""
    conn.execute(sa.text("SELECT set_config('app.user_id', '', true)"))
    conn.execute(sa.text("SELECT set_config('app.service_role', '', true)"))
    for table in tables:
        conn.execute(sa.text(f"DROP POLICY IF EXISTS {name} ON {table}"))


@contextmanager
def migration_bypass(
    conn: sa.Connection,
    tables: Iterable[str],
    *,
    name: str = DEFAULT_MIGRATION_POLICY,
) -> Generator[None, None, None]:
    """Transient cross-tenant RLS bypass for Alembic data migrations.

    Creates a short-lived ``migration_bypass`` policy gated on
    ``app.service_role = 'migrator'``, sets that GUC, yields, then drops the
    policy on success. If the migration statement block raises, teardown is
    skipped and the enclosing Alembic transaction rollback removes the policy.
    """
    install_migration_bypass(conn, tables, name=name)
    try:
        yield
    except BaseException:
        raise
    else:
        remove_migration_bypass(conn, tables, name=name)
