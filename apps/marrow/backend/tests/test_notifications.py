"""Tests for notifications substrate (issue #304)."""

from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import unit_of_work
from app.database import get_db
from app.main import app
from app.services.notifications import NotificationService
from tests.helpers import make_tenant_get_db_override, signup_payload

pytestmark = pytest.mark.asyncio


async def _signup_client(async_db: AsyncSession, suffix: str) -> AsyncClient:
    app.dependency_overrides[get_db] = make_tenant_get_db_override(async_db)
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    email = f"notif_{suffix}@example.com"
    resp = await client.post(
        "/api/v1/auth/signup",
        json=signup_payload(email, "secure-pass-12", f"notif_{suffix}"),
    )
    assert resp.status_code == 200
    return client


async def test_notify_inserts_for_other_user(
    async_db: AsyncSession,
    authed_client: AsyncClient,
):
    recipient_client = await _signup_client(async_db, uuid.uuid4().hex[:8])
    recipient_me = await recipient_client.get("/api/v1/auth/me")
    recipient_id = uuid.UUID(recipient_me.json()["user_id"])

    service = NotificationService(async_db)
    async with unit_of_work(async_db):
        await service.notify(recipient_id, "connection_request", {"handle": "sender"})

    listed = await recipient_client.get("/api/v1/notifications")
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["type"] == "connection_request"

    sender_list = await authed_client.get("/api/v1/notifications")
    assert sender_list.json() == []


async def test_unread_count_and_mark_read(authed_client: AsyncClient, async_db: AsyncSession):
    me = await authed_client.get("/api/v1/auth/me")
    user_id = uuid.UUID(me.json()["user_id"])
    service = NotificationService(async_db)
    async with unit_of_work(async_db):
        await service.notify(user_id, "connection_request", {"handle": "x"})
        await service.notify(user_id, "connection_accepted", {"handle": "y"})

    count = await authed_client.get("/api/v1/notifications/unread-count")
    assert count.json()["count"] == 2

    listed = await authed_client.get("/api/v1/notifications")
    first_id = listed.json()[0]["id"]
    await authed_client.post("/api/v1/notifications/read", json={"ids": [first_id]})
    count_after = await authed_client.get("/api/v1/notifications/unread-count")
    assert count_after.json()["count"] == 1

    await authed_client.post("/api/v1/notifications/read", json={"all": True})
    cleared = await authed_client.get("/api/v1/notifications/unread-count")
    assert cleared.json()["count"] == 0
