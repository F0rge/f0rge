from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

from f0rge_db.auth_context import user_id_ctx
from f0rge_db.tenant import apply_session_user_id
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.main import app


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


async def signup_client(
    async_db: AsyncSession,
    email: str,
    password: str = "secure-pass-12",
    handle: str | None = None,
) -> AsyncClient:
    """Sign up a fresh user over HTTP and return an authed client for them.

    Installs the tenant-aware ``get_db`` override on the app; tests that care
    about cleanup pop it in a ``finally``.
    """
    app.dependency_overrides[get_db] = make_tenant_get_db_override(async_db)
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    resp = await client.post("/api/v1/auth/signup", json=signup_payload(email, password, handle))
    assert resp.status_code == 200
    return client


async def create_treatment(
    client: AsyncClient, doses_per_day: int = 2, name: str = "Rifaximin"
) -> int:
    """Create a dose-tracked treatment via the API; returns its id."""
    resp = await client.post(
        "/api/v1/treatments",
        json={
            "name": name,
            "type": "prescription",
            "start_date": "2026-07-01",
            "doses_per_day": doses_per_day,
        },
    )
    assert resp.status_code == 201
    return resp.json()["id"]
