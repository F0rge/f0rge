from __future__ import annotations

import uuid

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from f0rge_core.exceptions import UnauthorizedError
from f0rge_db.auth_context import user_id_ctx
from f0rge_db.rls import MIGRATION_DUMMY_USER_ID


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

    Also sets ``user_id_ctx`` so ``owned_by_user`` / ``current_user_id()`` work
    in background workers and other non-request code paths that call this helper.

    Uses session-scoped config (``is_local=false``) so values survive ``COMMIT``
    within the same request — transaction-local config is cleared on commit and
    breaks ``refresh()`` after writes.
    """
    user_id_ctx.set(user_id)
    await session.execute(
        sa.text("SELECT set_config('app.user_id', :user_id, false)"),
        {"user_id": str(user_id)},
    )


async def apply_service_role(session: AsyncSession, role: str) -> None:
    """Set Postgres ``app.service_role`` for privileged background/MCP auth paths.

    Also stamps ``app.user_id`` with the nil UUID sentinel. Under FORCE RLS,
    Postgres evaluates every PERMISSIVE policy; ``tenant_isolation`` casts
    ``app.user_id`` to uuid and throws on ``''`` even when a service-role
    policy would allow the row. Never leave the GUC as empty string — use
    ``clear_tenant_session`` (RESET) or this sentinel.
    """
    await session.execute(
        sa.text("SELECT set_config('app.service_role', :role, false)"),
        {"role": role},
    )
    await session.execute(
        sa.text("SELECT set_config('app.user_id', :user_id, false)"),
        {"user_id": MIGRATION_DUMMY_USER_ID},
    )


async def clear_tenant_session(session: AsyncSession) -> None:
    """Reset tenant GUCs before returning a pooled connection.

    Use ``RESET`` — not ``set_config(..., '')`` — so RLS policies that cast
    ``current_setting('app.user_id', true)::uuid`` never see an empty string.
    """
    await session.execute(sa.text("RESET app.user_id"))
    await session.execute(sa.text("RESET app.service_role"))
