"""Tests for social groups (issue #306)."""

from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.main import app
from tests.helpers import make_tenant_get_db_override, signup_payload

pytestmark = pytest.mark.asyncio
PASSWORD = "secure-pass-12"


async def _signup_client(async_db: AsyncSession, suffix: str) -> AsyncClient:
    app.dependency_overrides[get_db] = make_tenant_get_db_override(async_db)
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    handle = f"grp_{suffix}"
    resp = await client.post(
        "/api/v1/auth/signup",
        json=signup_payload(f"{handle}@example.com", PASSWORD, handle),
    )
    assert resp.status_code == 200
    return client


async def _connect_users(a: AsyncClient, b: AsyncClient) -> None:
    b_handle = (await b.get("/api/v1/auth/me")).json()["handle"]
    sent = await a.post("/api/v1/social/connections", json={"handle": b_handle})
    assert sent.status_code == 201
    conn_id = sent.json()["id"]
    accepted = await b.post(f"/api/v1/social/connections/{conn_id}/accept")
    assert accepted.status_code == 200


async def test_group_happy_path(async_db: AsyncSession):
    owner = await _signup_client(async_db, uuid.uuid4().hex[:6])
    member = await _signup_client(async_db, uuid.uuid4().hex[:6])
    await _connect_users(owner, member)
    member_handle = (await member.get("/api/v1/auth/me")).json()["handle"]

    created = await owner.post("/api/v1/social/groups", json={"name": "our family"})
    assert created.status_code == 201
    body = created.json()
    group_id = body["id"]
    assert body["name"] == "our family"
    assert body["my_role"] == "owner"
    assert body["my_status"] == "joined"
    assert body["member_count"] == 1

    invited = await owner.post(
        f"/api/v1/social/groups/{group_id}/invite",
        json={"handle": member_handle},
    )
    assert invited.status_code == 201
    assert invited.json()["status"] == "invited"

    unread = await member.get("/api/v1/notifications/unread-count")
    assert unread.json()["count"] >= 1

    accepted = await member.post(f"/api/v1/social/groups/{group_id}/accept")
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "joined"

    detail = await member.get(f"/api/v1/social/groups/{group_id}")
    assert detail.status_code == 200
    assert detail.json()["member_count"] == 2
    assert len(detail.json()["members"]) == 2


async def test_invite_requires_connection(async_db: AsyncSession):
    owner = await _signup_client(async_db, uuid.uuid4().hex[:6])
    stranger = await _signup_client(async_db, uuid.uuid4().hex[:6])
    stranger_handle = (await stranger.get("/api/v1/auth/me")).json()["handle"]

    created = await owner.post("/api/v1/social/groups", json={"name": "closed"})
    group_id = created.json()["id"]

    resp = await owner.post(
        f"/api/v1/social/groups/{group_id}/invite",
        json={"handle": stranger_handle},
    )
    assert resp.status_code == 400


async def test_decline_and_reinvite(async_db: AsyncSession):
    owner = await _signup_client(async_db, uuid.uuid4().hex[:6])
    member = await _signup_client(async_db, uuid.uuid4().hex[:6])
    await _connect_users(owner, member)
    member_handle = (await member.get("/api/v1/auth/me")).json()["handle"]

    group_id = (await owner.post("/api/v1/social/groups", json={"name": "retry"})).json()["id"]
    await owner.post(
        f"/api/v1/social/groups/{group_id}/invite",
        json={"handle": member_handle},
    )

    declined = await member.delete(f"/api/v1/social/groups/{group_id}/members/{member_handle}")
    assert declined.status_code == 204

    reinvited = await owner.post(
        f"/api/v1/social/groups/{group_id}/invite",
        json={"handle": member_handle},
    )
    assert reinvited.status_code == 201


async def test_duplicate_invite_409(async_db: AsyncSession):
    owner = await _signup_client(async_db, uuid.uuid4().hex[:6])
    member = await _signup_client(async_db, uuid.uuid4().hex[:6])
    await _connect_users(owner, member)
    member_handle = (await member.get("/api/v1/auth/me")).json()["handle"]

    group_id = (await owner.post("/api/v1/social/groups", json={"name": "dup"})).json()["id"]
    await owner.post(
        f"/api/v1/social/groups/{group_id}/invite",
        json={"handle": member_handle},
    )
    dup = await owner.post(
        f"/api/v1/social/groups/{group_id}/invite",
        json={"handle": member_handle},
    )
    assert dup.status_code == 409


async def test_leave_and_owner_cannot_leave(async_db: AsyncSession):
    owner = await _signup_client(async_db, uuid.uuid4().hex[:6])
    member = await _signup_client(async_db, uuid.uuid4().hex[:6])
    await _connect_users(owner, member)
    owner_handle = (await owner.get("/api/v1/auth/me")).json()["handle"]
    member_handle = (await member.get("/api/v1/auth/me")).json()["handle"]

    group_id = (await owner.post("/api/v1/social/groups", json={"name": "leave test"})).json()["id"]
    await owner.post(
        f"/api/v1/social/groups/{group_id}/invite",
        json={"handle": member_handle},
    )
    await member.post(f"/api/v1/social/groups/{group_id}/accept")

    left = await member.delete(f"/api/v1/social/groups/{group_id}/members/{member_handle}")
    assert left.status_code == 204

    owner_leave = await owner.delete(f"/api/v1/social/groups/{group_id}/members/{owner_handle}")
    assert owner_leave.status_code == 400


async def test_owner_kick_and_non_owner_forbidden(async_db: AsyncSession):
    owner = await _signup_client(async_db, uuid.uuid4().hex[:6])
    member = await _signup_client(async_db, uuid.uuid4().hex[:6])
    other = await _signup_client(async_db, uuid.uuid4().hex[:6])
    await _connect_users(owner, member)
    await _connect_users(owner, other)
    member_handle = (await member.get("/api/v1/auth/me")).json()["handle"]

    group_id = (await owner.post("/api/v1/social/groups", json={"name": "kick test"})).json()["id"]
    await owner.post(
        f"/api/v1/social/groups/{group_id}/invite",
        json={"handle": member_handle},
    )
    await member.post(f"/api/v1/social/groups/{group_id}/accept")

    kicked = await owner.delete(f"/api/v1/social/groups/{group_id}/members/{member_handle}")
    assert kicked.status_code == 204

    forbidden = await member.delete(f"/api/v1/social/groups/{group_id}/members/{member_handle}")
    assert forbidden.status_code in (400, 404)


async def test_rename_and_delete_owner_only(async_db: AsyncSession):
    owner = await _signup_client(async_db, uuid.uuid4().hex[:6])
    member = await _signup_client(async_db, uuid.uuid4().hex[:6])
    await _connect_users(owner, member)
    member_handle = (await member.get("/api/v1/auth/me")).json()["handle"]

    group_id = (await owner.post("/api/v1/social/groups", json={"name": "old name"})).json()["id"]
    await owner.post(
        f"/api/v1/social/groups/{group_id}/invite",
        json={"handle": member_handle},
    )
    await member.post(f"/api/v1/social/groups/{group_id}/accept")

    denied = await member.patch(
        f"/api/v1/social/groups/{group_id}",
        json={"name": "hijacked"},
    )
    assert denied.status_code == 400

    renamed = await owner.patch(
        f"/api/v1/social/groups/{group_id}",
        json={"name": "new name"},
    )
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "new name"

    delete_denied = await member.delete(f"/api/v1/social/groups/{group_id}")
    assert delete_denied.status_code == 400

    deleted = await owner.delete(f"/api/v1/social/groups/{group_id}")
    assert deleted.status_code == 204

    missing = await owner.get(f"/api/v1/social/groups/{group_id}")
    assert missing.status_code == 404


async def test_stranger_sees_empty_and_404(async_db: AsyncSession):
    owner = await _signup_client(async_db, uuid.uuid4().hex[:6])
    stranger = await _signup_client(async_db, uuid.uuid4().hex[:6])

    group_id = (await owner.post("/api/v1/social/groups", json={"name": "private"})).json()["id"]

    listing = await stranger.get("/api/v1/social/groups")
    assert listing.status_code == 200
    assert listing.json()["groups"] == []

    detail = await stranger.get(f"/api/v1/social/groups/{group_id}")
    assert detail.status_code == 404


async def test_group_detail_no_recursion_error(async_db: AsyncSession):
    owner = await _signup_client(async_db, uuid.uuid4().hex[:6])
    member = await _signup_client(async_db, uuid.uuid4().hex[:6])
    await _connect_users(owner, member)
    member_handle = (await member.get("/api/v1/auth/me")).json()["handle"]

    group_id = (await owner.post("/api/v1/social/groups", json={"name": "rls check"})).json()["id"]
    await owner.post(
        f"/api/v1/social/groups/{group_id}/invite",
        json={"handle": member_handle},
    )

    detail = await member.get(f"/api/v1/social/groups/{group_id}")
    assert detail.status_code == 200
    assert detail.json()["name"] == "rls check"
