"""Two-user tenant isolation tests for issue #214."""

from __future__ import annotations

import datetime
import uuid
from typing import AsyncIterator
from unittest.mock import AsyncMock, patch

from httpx import ASGITransport, AsyncClient
from mcp.server.fastmcp import FastMCP
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth_context import user_id_ctx
from app.database import get_db
from app.main import app
from app.mcp import tools as t_mod
from app.models.entry import Entry
from app.models.user import LEO_PLACEHOLDER_PASSWORD_HASH, User
from app.tenant import apply_session_user_id, owned_by_user

PASSWORD = "tenant-test-password-12"
_ENTRY_PAYLOAD = {
    "date": "2026-04-01",
    "overall": 2,
    "bloating": 0,
    "stool_status": "normal",
    "joint_pain": 0,
    "neuro": 0,
    "sleep_quality": 2,
    "stress": 1,
    "diet_risk": "",
    "supplements": "",
    "sick": False,
}


async def _signup_client(async_db: AsyncSession, email: str) -> AsyncClient:
    async def _override_get_db() -> AsyncIterator[AsyncSession]:
        yield async_db

    app.dependency_overrides[get_db] = _override_get_db
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    resp = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": PASSWORD},
    )
    assert resp.status_code == 200
    return client


async def test_user_b_cannot_read_user_a_entry(async_db: AsyncSession) -> None:
    client_a = await _signup_client(async_db, "tenant-a@example.com")
    client_b = await _signup_client(async_db, "tenant-b@example.com")
    try:
        me_a = await client_a.get("/api/v1/auth/me")
        user_a = uuid.UUID(me_a.json()["user_id"])

        created = await client_a.post("/api/v1/entries", json=_ENTRY_PAYLOAD)
        assert created.status_code == 201

        listed = await client_b.get("/api/v1/entries")
        assert listed.status_code == 200
        assert listed.json() == []

        fetched = await client_b.get("/api/v1/entries/2026-04-01")
        assert fetched.status_code == 404
    finally:
        await client_a.aclose()
        await client_b.aclose()
        app.dependency_overrides.pop(get_db, None)

    token = user_id_ctx.set(user_a)
    try:
        row = (
            await async_db.execute(
                select(Entry).where(
                    owned_by_user(Entry.user_id),
                    Entry.date == datetime.date(2026, 4, 1),
                )
            )
        ).scalar_one_or_none()
    finally:
        user_id_ctx.reset(token)
    assert row is not None
    assert row.user_id == user_a


async def test_mcp_get_entry_scoped_to_authenticated_user(async_db: AsyncSession) -> None:
    user_a = uuid.uuid4()
    user_b = uuid.uuid4()
    async_db.add_all(
        [
            User(id=user_a, email="mcp-a@example.com", password_hash=LEO_PLACEHOLDER_PASSWORD_HASH),
            User(id=user_b, email="mcp-b@example.com", password_hash=LEO_PLACEHOLDER_PASSWORD_HASH),
        ]
    )
    await async_db.flush()
    async_db.add(
        Entry(
            user_id=user_a,
            date=datetime.date(2026, 5, 1),
            overall=2,
            bloating=0,
            stool_normal=True,
            joint_pain=0,
            neuro=0,
            sleep_quality=2,
            stress=1,
            diet_risk="",
            supplements="",
            sick=False,
            hot_shower=False,
        )
    )
    await async_db.flush()

    class _Ctx:
        client_id = str(user_b)

    scoped_session = AsyncMock()
    scoped_session.__aenter__ = AsyncMock(return_value=async_db)
    scoped_session.__aexit__ = AsyncMock(return_value=False)

    token = user_id_ctx.set(user_b)
    await apply_session_user_id(async_db, user_b)
    try:
        with patch("app.mcp.tools.scoped_ro_session", return_value=scoped_session):
            server = FastMCP("test")
            t_mod.register_tools(server)
            tool_fn = next(t for t in server._tool_manager.list_tools() if t.name == "get_entry").fn
            result = await tool_fn(date="2026-05-01", ctx=_Ctx())
    finally:
        user_id_ctx.reset(token)

    assert result is None
