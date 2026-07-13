"""Group meal tagging (issue #349)."""

from __future__ import annotations

import json
import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from tests.test_social_meal_tags import (
    DAY,
    _connect_users,
    _ensure_entry,
    _jpg_bytes,
    _signup_client,
)

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def group_tag_storage(
    async_db: AsyncSession, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    photo_dir = tmp_path / "photos"
    photo_dir.mkdir()
    monkeypatch.setattr(settings, "photo_dir", str(photo_dir))
    monkeypatch.setattr(settings, "food_analysis_enabled", False)

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


async def test_tag_group_fans_out_to_joined_connected_members(
    async_db: AsyncSession,
    group_tag_storage: None,
) -> None:
    owner = await _signup_client(async_db, uuid.uuid4().hex[:6])
    member_a = await _signup_client(async_db, uuid.uuid4().hex[:6])
    member_b = await _signup_client(async_db, uuid.uuid4().hex[:6])
    outsider = await _signup_client(async_db, uuid.uuid4().hex[:6])

    await _connect_users(owner, member_a)
    await _connect_users(owner, member_b)

    member_a_handle = (await member_a.get("/api/v1/auth/me")).json()["handle"]
    member_b_handle = (await member_b.get("/api/v1/auth/me")).json()["handle"]
    outsider_handle = (await outsider.get("/api/v1/auth/me")).json()["handle"]

    group_id = (await owner.post("/api/v1/social/groups", json={"name": "lunch crew"})).json()["id"]
    for handle in (member_a_handle, member_b_handle, outsider_handle):
        await owner.post(f"/api/v1/social/groups/{group_id}/invite", json={"handle": handle})

    await member_a.post(f"/api/v1/social/groups/{group_id}/accept")
    await member_b.post(f"/api/v1/social/groups/{group_id}/accept")
    await outsider.post(f"/api/v1/social/groups/{group_id}/accept")

    await _ensure_entry(owner)
    uploaded = await owner.post(
        f"/api/v1/entries/{DAY.isoformat()}/photos",
        files={"file": ("meal.jpg", _jpg_bytes(), "image/jpeg")},
        data={"tagged_group_ids": json.dumps([group_id])},
    )
    assert uploaded.status_code == 201

    tags = await owner.get(f"/api/v1/photos/{uploaded.json()['id']}/tags")
    handles = {t["user"]["handle"] for t in tags.json()["tags"]}
    assert member_a_handle in handles
    assert member_b_handle in handles
    assert outsider_handle not in handles

    incoming_a = (await member_a.get("/api/v1/social/meal-tags")).json()["incoming_pending"]
    incoming_b = (await member_b.get("/api/v1/social/meal-tags")).json()["incoming_pending"]
    assert len(incoming_a) >= 1
    assert len(incoming_b) >= 1
