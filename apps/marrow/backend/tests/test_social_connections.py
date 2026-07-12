"""Tests for social connections (issue #305)."""

from __future__ import annotations

import uuid
from typing import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.main import app
from tests.helpers import signup_payload

pytestmark = pytest.mark.asyncio
PASSWORD = "secure-pass-12"


async def _signup_client(async_db: AsyncSession, suffix: str) -> AsyncClient:
    async def _override_get_db() -> AsyncIterator[AsyncSession]:
        yield async_db

    app.dependency_overrides[get_db] = _override_get_db
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    handle = f"conn_{suffix}"
    resp = await client.post(
        "/api/v1/auth/signup",
        json=signup_payload(f"{handle}@example.com", PASSWORD, handle),
    )
    assert resp.status_code == 200
    return client


async def test_connection_happy_path(async_db: AsyncSession):
    a = await _signup_client(async_db, uuid.uuid4().hex[:6])
    b = await _signup_client(async_db, uuid.uuid4().hex[:6])
    b_handle = (await b.get("/api/v1/auth/me")).json()["handle"]

    sent = await a.post("/api/v1/social/connections", json={"handle": b_handle})
    assert sent.status_code == 201
    conn_id = sent.json()["id"]

    b_list = await b.get("/api/v1/social/connections")
    assert len(b_list.json()["pending_incoming"]) == 1

    unread = await b.get("/api/v1/notifications/unread-count")
    assert unread.json()["count"] >= 1

    accepted = await b.post(f"/api/v1/social/connections/{conn_id}/accept")
    assert accepted.status_code == 200

    a_list = await a.get("/api/v1/social/connections")
    assert len(a_list.json()["accepted"]) == 1


async def test_self_connect_400(async_db: AsyncSession):
    client = await _signup_client(async_db, uuid.uuid4().hex[:6])
    handle = (await client.get("/api/v1/auth/me")).json()["handle"]
    resp = await client.post("/api/v1/social/connections", json={"handle": handle})
    assert resp.status_code == 400


async def test_duplicate_request_409(async_db: AsyncSession):
    a = await _signup_client(async_db, uuid.uuid4().hex[:6])
    b = await _signup_client(async_db, uuid.uuid4().hex[:6])
    b_handle = (await b.get("/api/v1/auth/me")).json()["handle"]
    await a.post("/api/v1/social/connections", json={"handle": b_handle})
    dup = await a.post("/api/v1/social/connections", json={"handle": b_handle})
    assert dup.status_code == 409
