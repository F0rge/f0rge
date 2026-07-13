"""Prefix user search for Connections add flow."""

from __future__ import annotations


import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.main import app
from tests.helpers import make_tenant_get_db_override, signup_payload

pytestmark = pytest.mark.asyncio
PASSWORD = "secure-pass-12"


async def _signup_client(async_db: AsyncSession, suffix: str) -> AsyncClient:
    app.dependency_overrides[get_db] = make_tenant_get_db_override(async_db)
    client = AsyncClient(
        transport=__import__("httpx").ASGITransport(app=app), base_url="http://test"
    )
    handle = f"srch_{suffix}"
    resp = await client.post(
        "/api/v1/auth/signup",
        json=signup_payload(f"{handle}@example.com", PASSWORD, handle),
    )
    assert resp.status_code == 200
    return client


async def test_search_returns_prefix_matches_excluding_self(async_db: AsyncSession):
    searcher = await _signup_client(async_db, "me")
    await _signup_client(async_db, "leo1")
    await _signup_client(async_db, "leo2")
    await _signup_client(async_db, "other")

    resp = await searcher.get("/api/v1/social/users/search?q=srch_leo")
    assert resp.status_code == 200
    handles = {u["handle"] for u in resp.json()["users"]}
    assert handles == {"srch_leo1", "srch_leo2"}
    assert "srch_other" not in handles
    assert "srch_me" not in handles


async def test_search_respects_limit(async_db: AsyncSession):
    searcher = await _signup_client(async_db, "lim")
    for i in range(5):
        await _signup_client(async_db, f"lim{i}")

    resp = await searcher.get("/api/v1/social/users/search?q=srch_lim&limit=3")
    assert resp.status_code == 200
    assert len(resp.json()["users"]) == 3


async def test_search_reports_connection_status(async_db: AsyncSession):
    searcher = await _signup_client(async_db, "a")
    target = await _signup_client(async_db, "btarget")
    target_handle = (await target.get("/api/v1/auth/me")).json()["handle"]

    before = await searcher.get("/api/v1/social/users/search?q=srch_btarget")
    assert before.json()["users"][0]["connection_status"] == "none"

    sent = await searcher.post("/api/v1/social/connections", json={"handle": target_handle})
    assert sent.status_code == 201

    after = await searcher.get("/api/v1/social/users/search?q=srch_btarget")
    assert after.json()["users"][0]["connection_status"] == "pending_outgoing"


async def test_search_requires_min_three_chars(async_db: AsyncSession):
    searcher = await _signup_client(async_db, "short")
    resp = await searcher.get("/api/v1/social/users/search?q=ab")
    assert resp.status_code == 200
    assert resp.json()["users"] == []
