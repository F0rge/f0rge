from __future__ import annotations

import uuid

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.auth_context import user_id_ctx
from app.exceptions import UnauthorizedError


def current_user_id() -> uuid.UUID:
    """Return the authenticated user id from request context."""
    user_id = user_id_ctx.get()
    if user_id is None:
        raise UnauthorizedError("Not authenticated")
    return user_id


def owned_by_user(column: InstrumentedAttribute[uuid.UUID]) -> sa.ColumnElement[bool]:
    """SQLAlchemy filter: row belongs to the current user."""
    return column == current_user_id()


async def apply_session_user_id(session: AsyncSession, user_id: uuid.UUID) -> None:
    """Set Postgres ``app.user_id`` for RLS policies for this connection.

    Uses session-scoped config (``is_local=false``) so values survive ``COMMIT``
    within the same request — transaction-local config is cleared on commit and
    breaks ``refresh()`` after writes.
    """
    await session.execute(
        sa.text("SELECT set_config('app.user_id', :user_id, false)"),
        {"user_id": str(user_id)},
    )


async def apply_service_role(session: AsyncSession, role: str) -> None:
    """Set Postgres ``app.service_role`` for privileged background/MCP auth paths."""
    await session.execute(
        sa.text("SELECT set_config('app.service_role', :role, false)"),
        {"role": role},
    )


async def clear_tenant_session(session: AsyncSession) -> None:
    """Reset tenant GUCs before returning a pooled connection."""
    await session.execute(sa.text("SELECT set_config('app.user_id', '', false)"))
    await session.execute(sa.text("SELECT set_config('app.service_role', '', false)"))
