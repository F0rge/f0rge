"""Explicit operator boundary, never invoked by Railway preDeploy or API boot.

Run only after backup/restore and staff-access rehearsal in the deployment runbook.
Connections come from the environment; never put credentials on argv.
"""

from __future__ import annotations

import argparse
import asyncio
import os

import sqlalchemy as sa
from f0rge_db.db_url import resolve_database_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.config import settings
from app.runtime_database import verify_isolation_stage, verify_runtime_role


async def activate_rls(owner: AsyncSession, runtime: AsyncSession) -> None:
    """Verify actual runtime credentials before transactional ENABLE/FORCE.

    Caller commits the owner transaction then verifies runtime protection. A failed
    precondition leaves all tables unchanged. Runtime must connect to the same DB.
    """
    if settings.tenant_isolation_mode != "enforced" or not settings.frontend_proxy_secret:
        raise RuntimeError("Cutover requires enforced mode and FRONTEND_PROXY_SECRET")
    await verify_runtime_role(runtime, require_rls=False)
    identity = sa.text("SELECT current_database(), inet_server_addr(), inet_server_port()")
    if (await owner.execute(identity)).one() != (await runtime.execute(identity)).one():
        raise RuntimeError("Migration and runtime connections must target the same database")
    tables = list(
        await owner.scalars(
            sa.text("""SELECT c.relname FROM pg_class c
            JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname='public' AND c.relkind='r'
            AND EXISTS (SELECT 1 FROM pg_attribute a
                        WHERE a.attrelid=c.oid AND a.attname='team_id')
            AND c.relname NOT IN ('users','memberships') ORDER BY c.relname""")
        )
    )
    if not tables:
        raise RuntimeError("Tenant schema has not been migrated")
    for table in tables:
        policy = await owner.scalar(
            sa.text("""SELECT count(*) FROM pg_policies WHERE schemaname='public'
            AND tablename=:table AND policyname='organisation_isolation'"""),
            {"table": table},
        )
        if policy != 1:
            raise RuntimeError("Migrate all tenant policies before activation")
        grants = await runtime.scalar(
            sa.text("""SELECT bool_and(has_table_privilege(current_user, :table, privilege))
            FROM unnest(ARRAY['SELECT','INSERT','UPDATE','DELETE']) AS privilege"""),
            {"table": f'public."{table}"'},
        )
        if not grants:
            raise RuntimeError("Runtime role lacks application DML grants")
    # Names come from pg_catalog; quote identifiers even though schema is controlled.
    for table in tables:
        quoted = '"' + table.replace('"', '""') + '"'
        await owner.execute(sa.text(f"ALTER TABLE public.{quoted} ENABLE ROW LEVEL SECURITY"))
        await owner.execute(sa.text(f"ALTER TABLE public.{quoted} FORCE ROW LEVEL SECURITY"))


async def deactivate_rls(owner: AsyncSession) -> None:
    """Rollback only before a second tenant exists; traffic/jobs must be stopped."""
    if settings.tenant_isolation_mode != "single_home":
        raise RuntimeError("Rollback requires single_home mode")
    home = await owner.scalar(
        sa.text("SELECT count(*) = 1 AND bool_and(slug='firstout') FROM teams")
    )
    if not home:
        raise RuntimeError("Cannot remove isolation after additional tenants exist")
    tables = list(
        await owner.scalars(
            sa.text("""SELECT tablename FROM pg_policies WHERE schemaname='public'
            AND policyname='organisation_isolation' ORDER BY tablename""")
        )
    )
    for table in tables:
        quoted = '"' + table.replace('"', '""') + '"'
        await owner.execute(sa.text(f"ALTER TABLE public.{quoted} NO FORCE ROW LEVEL SECURITY"))
        await owner.execute(sa.text(f"ALTER TABLE public.{quoted} DISABLE ROW LEVEL SECURITY"))
    await verify_isolation_stage(owner)


async def run(action: str) -> None:
    owner_url = os.environ.get("MIGRATION_DATABASE_URL")
    if not owner_url:
        raise RuntimeError("Explicit MIGRATION_DATABASE_URL required; no runtime fallback")
    owner_engine = create_async_engine(resolve_database_url(owner_url))
    runtime_engine = create_async_engine(
        resolve_database_url(settings.database_url, direct_url=settings.direct_database_url)
    )
    try:
        async with AsyncSession(owner_engine) as owner, AsyncSession(runtime_engine) as runtime:
            async with owner.begin():
                if action == "activate":
                    await activate_rls(owner, runtime)
                else:
                    await deactivate_rls(owner)
            if action == "activate":
                await runtime.rollback()
                await verify_runtime_role(runtime)
    finally:
        await owner_engine.dispose()
        await runtime_engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("activate", "deactivate"))
    args = parser.parse_args()
    asyncio.run(run(args.action))
