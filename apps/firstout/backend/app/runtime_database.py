"""Production startup gate: tenant RLS must apply to the actual runtime role."""

from __future__ import annotations

import re

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession


async def verify_runtime_role(session: AsyncSession, *, require_rls: bool = True) -> None:
    role = (
        await session.execute(
            sa.text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname=current_user")
        )
    ).one()
    can_assume_bypass = await session.scalar(
        sa.text("""SELECT EXISTS (SELECT 1 FROM pg_roles
        WHERE (rolsuper OR rolbypassrls) AND pg_has_role(current_user, oid, 'MEMBER'))""")
    )
    owns_business_tables = await session.scalar(
        sa.text("""
        SELECT EXISTS (
          SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
          WHERE n.nspname='public' AND c.relkind='r'
            AND pg_has_role(current_user, c.relowner, 'MEMBER')
        )""")
    )
    if role.rolsuper or role.rolbypassrls or can_assume_bypass or owns_business_tables:
        raise RuntimeError(
            "Firstout runtime requires a non-owner NOSUPERUSER NOBYPASSRLS database role"
        )

    await verify_tenant_policies(session)
    if not require_rls:
        return

    unprotected = await session.scalar(
        sa.text("""
        SELECT EXISTS (
          SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
          WHERE n.nspname='public' AND c.relkind='r'
            AND EXISTS (SELECT 1 FROM pg_attribute a
                        WHERE a.attrelid=c.oid AND a.attname='team_id')
            AND c.relname NOT IN ('users','memberships')
            AND NOT (c.relrowsecurity AND c.relforcerowsecurity)
        )""")
    )
    if unprotected:
        raise RuntimeError("Firstout business tables require FORCE ROW LEVEL SECURITY")


async def verify_isolation_stage(session: AsyncSession) -> None:
    """A compatibility deployment must never masquerade as enforced tenancy."""
    import logging

    from app.config import settings

    if settings.tenant_isolation_mode == "enforced":
        if not settings.frontend_proxy_secret:
            raise RuntimeError("Enforced tenancy requires FRONTEND_PROXY_SECRET")
        await verify_runtime_role(session)
        return
    if settings.clerk_enabled or settings.tenant_signup_enabled or settings.clerk_import_enabled:
        raise RuntimeError("Clerk and tenant signup require enforced tenancy")
    invalid_home = await session.scalar(
        sa.text("SELECT count(*) > 1 OR bool_or(slug <> 'firstout') FROM teams")
    )
    if invalid_home:
        raise RuntimeError("single_home requires only the original Firstout team")
    active_rls = await session.scalar(
        sa.text("""
        SELECT EXISTS (
          SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
          WHERE n.nspname='public' AND c.relkind='r'
            AND (c.relrowsecurity OR c.relforcerowsecurity)
            AND EXISTS (SELECT 1 FROM pg_attribute a
                        WHERE a.attrelid=c.oid AND a.attname='team_id')
        )""")
    )
    if active_rls:
        raise RuntimeError("RLS is already active; use enforced mode or an approved rollback")
    logging.getLogger(__name__).warning(
        "Firstout single_home compatibility: database tenant isolation is NOT enforced"
    )


async def verify_tenant_policies(session: AsyncSession) -> None:
    """The sole policy must be the prepared, symmetric tenant predicate."""
    rows = (
        await session.execute(
            sa.text("""
        SELECT c.relname, p.polname, p.polcmd::text AS polcmd, p.polpermissive, p.polroles,
               pg_get_expr(p.polqual, p.polrelid) AS qual,
               pg_get_expr(p.polwithcheck, p.polrelid) AS with_check
        FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        LEFT JOIN pg_policy p ON p.polrelid=c.oid
        WHERE n.nspname='public' AND c.relkind='r'
          AND EXISTS (SELECT 1 FROM pg_attribute a
                      WHERE a.attrelid=c.oid AND a.attname='team_id')
          AND c.relname NOT IN ('users','memberships')
    """)
        )
    ).all()
    expected = "team_id=NULLIFcurrent_setting'app.tenant_id',true,''::uuid"
    seen = set()
    if not rows:
        raise RuntimeError("Tenant schema has not been migrated")
    for row in rows:
        expressions = (row.qual, row.with_check)
        valid = (
            row.relname not in seen
            and row.polname == "organisation_isolation"
            and row.polcmd == "*"
            and row.polpermissive
            and list(row.polroles) == [0]
            and all(
                re.sub(r"[\s()]|::text", "", expression or "") == expected
                for expression in expressions
            )
        )
        if not valid:
            raise RuntimeError(
                "Tenant tables require the sole canonical organisation_isolation policy"
            )
        seen.add(row.relname)
