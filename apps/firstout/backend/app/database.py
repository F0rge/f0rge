"""Firstout database composition: organisation scope never changes Marrow user scope."""

from __future__ import annotations

from typing import AsyncIterator

from f0rge_db.engine import create_engine_and_sessionmaker
from f0rge_db.organisation import (
    apply_tenant_context,
    clear_organisation_session,
    organisation_session,
    register_organisation_hook,
    tenant_id_ctx,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Session

from app.config import settings


class TenantSession(Session):
    """Only Firstout sessions receive app.tenant_id transaction hooks."""


register_organisation_hook(TenantSession)
engine, _unused_session_maker = create_engine_and_sessionmaker(
    settings.database_url,
    direct_database_url=settings.direct_database_url,
)
async_session_maker = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession,
    sync_session_class=TenantSession,
)


class Base(DeclarativeBase):
    pass


def tenant_session(team_id=None):
    return organisation_session(async_session_maker, team_id)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with tenant_session() as session:
        yield session


__all__ = [
    "Base",
    "TenantSession",
    "engine",
    "async_session_maker",
    "get_db",
    "tenant_session",
    "apply_tenant_context",
    "clear_organisation_session",
    "tenant_id_ctx",
]
