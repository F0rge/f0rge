"""Production startup gate: tenant RLS must apply to the actual runtime role."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession


async def verify_runtime_role(session: AsyncSession) -> None:
    role = (
        await session.execute(
            sa.text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname=current_user")
        )
    ).one()
    owns_business_tables = await session.scalar(
        sa.text("""
        SELECT EXISTS (
          SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
          WHERE n.nspname='public' AND c.relkind='r'
            AND pg_has_role(current_user, c.relowner, 'MEMBER')
            AND EXISTS (SELECT 1 FROM pg_attribute a
                        WHERE a.attrelid=c.oid AND a.attname='team_id')
            AND c.relname NOT IN ('users','memberships')
        )""")
    )
    if role.rolsuper or role.rolbypassrls or owns_business_tables:
        raise RuntimeError(
            "Firstout runtime requires a non-owner NOSUPERUSER NOBYPASSRLS database role"
        )

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
