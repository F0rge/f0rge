"""Composition module: Vellano engine/session from f0rge_db factories.

S0 has no domain tables yet. Later slices import ``Base`` and ``get_db`` here.
Never point this at Marrow ``DATABASE_URL``.
"""

from __future__ import annotations

from typing import AsyncIterator

from fastapi import HTTPException, status
from f0rge_db.auth_context import user_id_ctx
from f0rge_db.engine import create_engine_and_sessionmaker, register_rls_hook
from f0rge_db.tenant import apply_session_user_id, clear_tenant_session
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.config import settings
from app.tenancy.context import tenant_ctx
from app.tenancy.engines import engine_cache

engine, async_session_maker = create_engine_and_sessionmaker(
    settings.database_url,
    direct_database_url=settings.direct_database_url,
)

register_rls_hook()


def default_tenant_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Single-tenant startup fallback when the platform registry is unset."""
    return async_session_maker


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncIterator[AsyncSession]:
    tenant = tenant_ctx.get()
    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="tenant_not_found",
        )
    session_maker = await engine_cache.get_sessionmaker(tenant)
    async with session_maker() as session:
        user_id = user_id_ctx.get()
        try:
            if user_id is not None:
                await apply_session_user_id(session, user_id)
            yield session
        finally:
            await session.rollback()
            await clear_tenant_session(session)
