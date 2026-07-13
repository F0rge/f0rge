"""Notification clearing when social actions resolve (issue #348)."""

from __future__ import annotations

import datetime
import io
import json
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.main import app
from app.models.notification import Notification
from tests.helpers import make_tenant_get_db_override, signup_payload

pytestmark = pytest.mark.asyncio
PASSWORD = "secure-pass-12"
DAY = datetime.date(2026, 3, 20)
_ENTRY_PAYLOAD = {
    "date": DAY.isoformat(),
    "overall": 2,
    "bloating": 0,
    "stool_normal": True,
    "joint_pain": 0,
    "neuro": 0,
    "sleep_quality": 2,
    "stress": 1,
    "diet_risk": "normal",
    "supplements": "",
    "sick": False,
    "hot_shower": False,
}


def _jpg_bytes() -> bytes:
    img = Image.new("RGB", (12, 12), color="green")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


async def _ensure_entry(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/entries", json=_ENTRY_PAYLOAD)
    assert resp.status_code in (201, 409), resp.text


async def _signup_client(async_db: AsyncSession, suffix: str) -> AsyncClient:
    app.dependency_overrides[get_db] = make_tenant_get_db_override(async_db)
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    handle = f"nr_{suffix}"
    resp = await client.post(
        "/api/v1/auth/signup",
        json=signup_payload(f"{handle}@example.com", PASSWORD, handle),
    )
    assert resp.status_code == 200
    return client


async def _connect_users(a: AsyncClient, b: AsyncClient) -> str:
    b_handle = (await b.get("/api/v1/auth/me")).json()["handle"]
    sent = await a.post("/api/v1/social/connections", json={"handle": b_handle})
    assert sent.status_code == 201
    conn_id = sent.json()["id"]
    accepted = await b.post(f"/api/v1/social/connections/{conn_id}/accept")
    assert accepted.status_code == 200
    return conn_id


async def _unread(client: AsyncClient) -> int:
    return (await client.get("/api/v1/notifications/unread-count")).json()["count"]


async def _invite_notifications(async_db: AsyncSession, user_client: AsyncClient) -> list[Notification]:
    me_id = uuid.UUID((await user_client.get("/api/v1/auth/me")).json()["user_id"])
    rows = (
        await async_db.execute(
            select(Notification).where(Notification.user_id == me_id).order_by(Notification.created_at)
        )
    ).scalars().all()
    return list(rows)


@pytest_asyncio.fixture
async def patch_tag_delivery_maker(async_db: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    class _SessionCtx:
        def __init__(self, db: AsyncSession) -> None:
            self._db = db

        async def __aenter__(self) -> AsyncSession:
            return self._db

        async def __aexit__(self, *args: object) -> None:
            return None

    class _Maker:
        def __call__(self) -> _SessionCtx:
            return _SessionCtx(async_db)

    monkeypatch.setattr("app.services.tag_delivery.async_session_maker", _Maker())

    async def _noop_clear_tenant_session(_session: AsyncSession) -> None:
        return None

    monkeypatch.setattr(
        "app.services.tag_delivery.clear_tenant_session", _noop_clear_tenant_session
    )


async def test_accept_connection_clears_connection_request_notification(async_db: AsyncSession):
    requester = await _signup_client(async_db, uuid.uuid4().hex[:6])
    recipient = await _signup_client(async_db, uuid.uuid4().hex[:6])

    recipient_handle = (await recipient.get("/api/v1/auth/me")).json()["handle"]
    sent = await requester.post("/api/v1/social/connections", json={"handle": recipient_handle})
    conn_id = sent.json()["id"]

    before = await _unread(recipient)
    assert before >= 1

    accepted = await recipient.post(f"/api/v1/social/connections/{conn_id}/accept")
    assert accepted.status_code == 200
    assert await _unread(recipient) == before - 1

    notes = await _invite_notifications(async_db, recipient)
    cleared = [n for n in notes if n.type == "connection_request"]
    assert cleared
    assert all(n.read_at is not None for n in cleared)


async def test_accept_group_invite_clears_group_invite_notification(async_db: AsyncSession):
    owner = await _signup_client(async_db, uuid.uuid4().hex[:6])
    member = await _signup_client(async_db, uuid.uuid4().hex[:6])
    await _connect_users(owner, member)
    member_handle = (await member.get("/api/v1/auth/me")).json()["handle"]

    group_id = (await owner.post("/api/v1/social/groups", json={"name": "dinner club"})).json()["id"]
    await owner.post(f"/api/v1/social/groups/{group_id}/invite", json={"handle": member_handle})

    before = await _unread(member)
    assert before >= 1

    accepted = await member.post(f"/api/v1/social/groups/{group_id}/accept")
    assert accepted.status_code == 200
    assert await _unread(member) == before - 1


async def test_decline_group_invite_clears_notification(async_db: AsyncSession):
    owner = await _signup_client(async_db, uuid.uuid4().hex[:6])
    member = await _signup_client(async_db, uuid.uuid4().hex[:6])
    await _connect_users(owner, member)
    member_handle = (await member.get("/api/v1/auth/me")).json()["handle"]

    group_id = (await owner.post("/api/v1/social/groups", json={"name": "maybe"})).json()["id"]
    await owner.post(f"/api/v1/social/groups/{group_id}/invite", json={"handle": member_handle})

    before = await _unread(member)
    declined = await member.post(f"/api/v1/social/groups/{group_id}/decline")
    assert declined.status_code == 204
    assert await _unread(member) == before - 1


async def test_approve_meal_tag_clears_meal_tag_request(
    async_db: AsyncSession,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    patch_tag_delivery_maker: None,
) -> None:
    photo_dir = tmp_path / "photos"
    photo_dir.mkdir()
    monkeypatch.setattr(settings, "photo_dir", str(photo_dir))
    monkeypatch.setattr(settings, "food_analysis_enabled", False)

    tagger = await _signup_client(async_db, uuid.uuid4().hex[:6])
    tagged = await _signup_client(async_db, uuid.uuid4().hex[:6])
    await _connect_users(tagger, tagged)
    tagged_handle = (await tagged.get("/api/v1/auth/me")).json()["handle"]

    await _ensure_entry(tagger)
    uploaded = await tagger.post(
        f"/api/v1/entries/{DAY.isoformat()}/photos",
        files={"file": ("meal.jpg", _jpg_bytes(), "image/jpeg")},
        data={"tagged_handles": json.dumps([tagged_handle])},
    )
    assert uploaded.status_code == 201
    photo_id = uploaded.json()["id"]

    tag_id = (await tagged.get("/api/v1/social/meal-tags")).json()["incoming_pending"][0]["id"]

    before = await _unread(tagged)
    assert before >= 1

    approved = await tagged.post(f"/api/v1/social/meal-tags/{tag_id}/approve")
    assert approved.status_code == 204
    assert await _unread(tagged) == before - 1


async def test_decline_meal_tag_clears_meal_tag_request(
    async_db: AsyncSession,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    patch_tag_delivery_maker: None,
) -> None:
    photo_dir = tmp_path / "photos"
    photo_dir.mkdir()
    monkeypatch.setattr(settings, "photo_dir", str(photo_dir))
    monkeypatch.setattr(settings, "food_analysis_enabled", False)

    tagger = await _signup_client(async_db, uuid.uuid4().hex[:6])
    tagged = await _signup_client(async_db, uuid.uuid4().hex[:6])
    await _connect_users(tagger, tagged)
    tagged_handle = (await tagged.get("/api/v1/auth/me")).json()["handle"]

    await _ensure_entry(tagger)
    uploaded = await tagger.post(
        f"/api/v1/entries/{DAY.isoformat()}/photos",
        files={"file": ("meal.jpg", _jpg_bytes(), "image/jpeg")},
        data={"tagged_handles": json.dumps([tagged_handle])},
    )
    assert uploaded.status_code == 201

    tag_id = (await tagged.get("/api/v1/social/meal-tags")).json()["incoming_pending"][0]["id"]

    before = await _unread(tagged)
    declined = await tagged.post(f"/api/v1/social/meal-tags/{tag_id}/decline")
    assert declined.status_code == 204
    assert await _unread(tagged) == before - 1
