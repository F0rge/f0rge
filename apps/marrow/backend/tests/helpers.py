from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

from f0rge_db.auth_context import user_id_ctx
from f0rge_db.tenant import apply_session_user_id
from sqlalchemy.ext.asyncio import AsyncSession


def signup_payload(
    email: str,
    password: str,
    handle: str | None = None,
) -> dict[str, str]:
    local = email.split("@")[0].replace(".", "_").replace("-", "_")
    chosen = handle or (local if len(local) >= 3 else f"u_{uuid.uuid4().hex[:8]}")
    return {"email": email, "password": password, "handle": chosen}


def make_tenant_get_db_override(async_db: AsyncSession):
    """Build a ``get_db`` override that applies the request tenant GUC."""

    async def _override_get_db() -> AsyncIterator[AsyncSession]:
        user_id = user_id_ctx.get()
        if user_id is not None:
            await apply_session_user_id(async_db, user_id)
        yield async_db

    return _override_get_db


async def yield_db_with_tenant_context(
    async_db: AsyncSession,
) -> AsyncIterator[AsyncSession]:
    """Async iterator for tests that wire ``get_db`` manually."""
    user_id = user_id_ctx.get()
    if user_id is not None:
        await apply_session_user_id(async_db, user_id)
    yield async_db
