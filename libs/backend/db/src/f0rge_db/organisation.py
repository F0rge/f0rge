"""Organisation-scoped transactions, independent of Marrow's user isolation.

Only opt-in session classes receive this hook. Values are transaction local;
commit/refresh starts a new transaction and re-applies the session's context.
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from contextvars import ContextVar
from typing import AsyncIterator

import sqlalchemy as sa
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import Session

from f0rge_core.exceptions import UnauthorizedError

tenant_id_ctx: ContextVar[uuid.UUID | None] = ContextVar("organisation_id", default=None)
_TENANT_KEY = "f0rge_organisation_id"


def current_tenant_id() -> uuid.UUID:
    value = tenant_id_ctx.get()
    if value is None:
        raise UnauthorizedError("Tenant context required")
    return value


def register_organisation_hook(session_class: type[Session]) -> None:
    """Register once on a dedicated Session subclass, never process-wide."""
    if session_class.__dict__.get("_organisation_hook_registered", False):
        return
    session_class._organisation_hook_registered = True

    @event.listens_for(session_class, "after_begin")
    def apply_on_begin(session, transaction, connection) -> None:
        tenant_id = session.info.get(_TENANT_KEY, tenant_id_ctx.get())
        if tenant_id is not None:
            connection.execute(
                sa.text("SELECT set_config('app.tenant_id', :tenant_id, true)"),
                {"tenant_id": str(tenant_id)},
            )


async def apply_tenant_context(session: AsyncSession, tenant_id: uuid.UUID) -> None:
    """Bind this session to a verified organisation, including its next transactions."""
    tenant_id = uuid.UUID(str(tenant_id))
    prior = session.info.get(_TENANT_KEY)
    if prior is not None and prior != tenant_id:
        raise UnauthorizedError("Cannot switch tenant within a database session")
    session.info[_TENANT_KEY] = tenant_id
    await session.execute(
        sa.text("SELECT set_config('app.tenant_id', :tenant_id, true)"),
        {"tenant_id": str(tenant_id)},
    )


async def clear_organisation_session(session: AsyncSession) -> None:
    """Rollback aborted work, RESET, and commit only that reset before pool return."""
    await session.rollback()
    session.info.pop(_TENANT_KEY, None)
    token = tenant_id_ctx.set(None)
    try:
        await session.execute(sa.text("RESET app.tenant_id"))
        await session.commit()
    finally:
        tenant_id_ctx.reset(token)


@asynccontextmanager
async def organisation_session(
    maker: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID | None = None
) -> AsyncIterator[AsyncSession]:
    """A request/job session with mandatory cleanup, including failed transactions."""
    resolved = tenant_id if tenant_id is not None else tenant_id_ctx.get()
    token = tenant_id_ctx.set(resolved)
    try:
        async with maker() as session:
            try:
                if resolved is not None:
                    await apply_tenant_context(session, resolved)
                yield session
            finally:
                await clear_organisation_session(session)
    finally:
        tenant_id_ctx.reset(token)
