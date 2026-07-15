"""Tests for social meal tagging (issue #307)."""

from __future__ import annotations

import datetime
import io
import json
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.main import app
from app.models.meal_tag import MealTag
from app.models.notification import Notification
from app.models.photo import Photo
from app.models.photo_analysis import PhotoAnalysis
from app.models.photo_ingredient import PhotoIngredient
from app.services.tag_delivery_background import deliver_tags_for_source_background
from f0rge_db.tenant import apply_session_user_id
from tests.helpers import make_tenant_get_db_override, signup_payload

pytestmark = pytest.mark.asyncio
PASSWORD = "secure-pass-12"
DAY = datetime.date(2026, 3, 15)


@pytest_asyncio.fixture
async def patch_tag_delivery_maker(async_db: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    """Route tag delivery through the test savepoint session (cross-connection invisible)."""

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


@pytest_asyncio.fixture
async def deferred_tag_storage(
    tmp_path, monkeypatch: pytest.MonkeyPatch, patch_tag_delivery_maker: None
) -> None:
    """Analysis pipeline enabled so tags stay pending until confirm."""
    photo_dir = tmp_path / "photos"
    photo_dir.mkdir()
    monkeypatch.setattr(settings, "photo_dir", str(photo_dir))
    monkeypatch.setattr(settings, "food_analysis_enabled", True)
    monkeypatch.setattr(settings, "openrouter_api_key", "sk-test-key")

    async def _fake_resolve_llm_credentials(_db):  # noqa: ANN001
        return "sk-test-key", "test-model"

    monkeypatch.setattr(
        "app.services.llm.factory.resolve_llm_credentials",
        _fake_resolve_llm_credentials,
    )

    async def _skip_auto_analysis(*_args, **_kwargs) -> None:
        return None

    monkeypatch.setattr(
        "app.services.food_analysis_orchestrator.FoodAnalysisOrchestrator.run",
        _skip_auto_analysis,
    )

    from app.services.meal_tags import MealTagService
    from app.services.tag_delivery import TagDeliveryService

    _original_create_tags = MealTagService.create_tags_for_photo

    async def _force_deferred_tags(
        self,
        photo,
        entry_date,
        tagged_handles_raw,
        *,
        analysis_will_run: bool,
    ):
        return await _original_create_tags(
            self,
            photo,
            entry_date,
            tagged_handles_raw,
            analysis_will_run=True,
        )

    monkeypatch.setattr(MealTagService, "create_tags_for_photo", _force_deferred_tags)

    async def _block_photo_only(self, *args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("photo-only delivery must not run in deferred_tag_storage tests")

    monkeypatch.setattr(TagDeliveryService, "process_photo_only_source", _block_photo_only)


@pytest_asyncio.fixture
async def storage(
    tmp_path, monkeypatch: pytest.MonkeyPatch, patch_tag_delivery_maker: None
) -> None:
    photo_dir = tmp_path / "photos"
    photo_dir.mkdir()
    monkeypatch.setattr(settings, "photo_dir", str(photo_dir))
    monkeypatch.setattr(settings, "food_analysis_enabled", False)
    monkeypatch.setattr(settings, "openrouter_api_key", "")

    async def _noop_analysis_run(self, photo_id: int, user_id=None) -> None:  # noqa: ANN001
        return None

    monkeypatch.setattr(
        "app.services.food_analysis_orchestrator.FoodAnalysisOrchestrator.run",
        _noop_analysis_run,
    )


async def _signup_client(async_db: AsyncSession, suffix: str) -> AsyncClient:
    app.dependency_overrides[get_db] = make_tenant_get_db_override(async_db)
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    handle = f"tag_{suffix}"
    resp = await client.post(
        "/api/v1/auth/signup",
        json=signup_payload(f"{handle}@example.com", PASSWORD, handle),
    )
    assert resp.status_code == 200
    return client


async def _connect_users(a: AsyncClient, b: AsyncClient) -> uuid.UUID:
    b_handle = (await b.get("/api/v1/auth/me")).json()["handle"]
    sent = await a.post("/api/v1/social/connections", json={"handle": b_handle})
    assert sent.status_code == 201
    conn_id = uuid.UUID(sent.json()["id"])
    accepted = await b.post(f"/api/v1/social/connections/{conn_id}/accept")
    assert accepted.status_code == 200
    return conn_id


def _jpg_bytes() -> bytes:
    img = Image.new("RGB", (12, 12), color="green")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


async def _ensure_entry(client: AsyncClient, day: datetime.date = DAY) -> None:
    resp = await client.post(
        "/api/v1/entries",
        json={
            "date": day.isoformat(),
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
        },
    )
    assert resp.status_code in (201, 409), resp.text


async def _upload_tagged(
    client: AsyncClient,
    *,
    handles: list[str],
    label: str = "Lunch",
    day: datetime.date = DAY,
) -> int:
    await _ensure_entry(client, day)
    files = {"file": ("meal.jpg", _jpg_bytes(), "image/jpeg")}
    data = {
        "label": label,
        "tagged_handles": json.dumps(handles),
    }
    resp = await client.post(f"/api/v1/entries/{day.isoformat()}/photos", files=files, data=data)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _user_id(client: AsyncClient) -> uuid.UUID:
    return uuid.UUID((await client.get("/api/v1/auth/me")).json()["user_id"])


async def _seed_confirmed_analysis(
    async_db: AsyncSession,
    photo_id: int,
    tagger_id: uuid.UUID,
    *,
    dish_name: str = "Spinach omelette",
) -> None:
    await apply_session_user_id(async_db, tagger_id)
    analysis = PhotoAnalysis(
        user_id=tagger_id,
        photo_id=photo_id,
        status="confirmed",
        dish_name=dish_name,
        cuisine="western",
        dish_confidence=0.9,
    )
    async_db.add(analysis)
    await async_db.flush()
    async_db.add(
        PhotoIngredient(
            user_id=tagger_id,
            analysis_id=analysis.id,
            name="spinach",
            canonical_name="spinach",
            visible=True,
            confidence=0.9,
            contains_gluten=False,
            histamine_score=1,
        )
    )
    await async_db.commit()


async def _recipient_photo_count_http(client: AsyncClient, day: datetime.date) -> int:
    resp = await client.get(f"/api/v1/entries/{day.isoformat()}")
    if resp.status_code == 404:
        return 0
    return len(resp.json().get("photos", []))


async def test_auto_mode_delivers_on_confirm(async_db: AsyncSession, deferred_tag_storage: None):
    day = datetime.date(2026, 4, 1)
    a = await _signup_client(async_db, uuid.uuid4().hex[:6])
    b = await _signup_client(async_db, uuid.uuid4().hex[:6])
    await _connect_users(a, b)
    b_handle = (await b.get("/api/v1/auth/me")).json()["handle"]

    mode = await b.put("/api/v1/settings/tagged-meal-mode", json={"tagged_meal_mode": "auto"})
    assert mode.status_code == 200

    photo_id = await _upload_tagged(a, handles=[b_handle], day=day)
    tagger_id = await _user_id(a)
    recipient_id = await _user_id(b)

    await apply_session_user_id(async_db, tagger_id)
    uploaded = await async_db.get(Photo, photo_id)
    assert uploaded is not None
    assert uploaded.user_id == tagger_id, (uploaded.user_id, tagger_id)

    outgoing = (await a.get("/api/v1/social/meal-tags")).json()["outgoing"]
    assert outgoing[0]["status"] == "delivered"

    assert await _recipient_photo_count_http(b, day) == 1

    await _seed_confirmed_analysis(async_db, photo_id, tagger_id)
    await deliver_tags_for_source_background(photo_id, tagger_id)

    assert await _recipient_photo_count_http(b, day) == 1

    entry_resp = await b.get(f"/api/v1/entries/{day.isoformat()}")
    delivered = entry_resp.json()["photos"][0]
    assert delivered["source_photo_id"] == photo_id

    outgoing = await a.get("/api/v1/social/meal-tags")
    assert outgoing.json()["outgoing"][0]["status"] == "delivered"

    await apply_session_user_id(async_db, recipient_id)
    notif_count = (
        await async_db.execute(
            select(func.count())
            .select_from(Notification)
            .where(Notification.type == "meal_tag_delivered")
        )
    ).scalar_one()
    assert notif_count >= 1


async def test_approve_mode_waits_for_approval(async_db: AsyncSession, deferred_tag_storage: None):
    a = await _signup_client(async_db, uuid.uuid4().hex[:6])
    b = await _signup_client(async_db, uuid.uuid4().hex[:6])
    await _connect_users(a, b)
    b_handle = (await b.get("/api/v1/auth/me")).json()["handle"]

    photo_id = await _upload_tagged(a, handles=[b_handle])
    assert await _recipient_photo_count_http(b, DAY) == 0

    incoming = await b.get("/api/v1/social/meal-tags")
    pending = incoming.json()["incoming_pending"]
    assert len(pending) == 1
    tag_id = pending[0]["id"]

    tagger_id = await _user_id(a)
    await _seed_confirmed_analysis(async_db, photo_id, tagger_id)
    await deliver_tags_for_source_background(photo_id, tagger_id)

    pending = (await b.get("/api/v1/social/meal-tags")).json()["incoming_pending"]
    assert pending[0]["source_dish_name"] == "Spinach omelette"

    approved = await b.post(f"/api/v1/social/meal-tags/{tag_id}/approve")
    assert approved.status_code == 204
    assert await _recipient_photo_count_http(b, DAY) == 1


async def test_decline_blocks_retag(async_db: AsyncSession, deferred_tag_storage: None):
    a = await _signup_client(async_db, uuid.uuid4().hex[:6])
    b = await _signup_client(async_db, uuid.uuid4().hex[:6])
    await _connect_users(a, b)
    b_handle = (await b.get("/api/v1/auth/me")).json()["handle"]

    photo_id = await _upload_tagged(a, handles=[b_handle])
    tagger_id = await _user_id(a)
    recipient_id = await _user_id(b)
    await _seed_confirmed_analysis(async_db, photo_id, tagger_id)
    await deliver_tags_for_source_background(photo_id, tagger_id)

    tag_id = (await b.get("/api/v1/social/meal-tags")).json()["incoming_pending"][0]["id"]
    declined = await b.post(f"/api/v1/social/meal-tags/{tag_id}/decline")
    assert declined.status_code == 204

    await apply_session_user_id(async_db, tagger_id)
    existing = (
        await async_db.execute(
            select(MealTag).where(
                MealTag.source_photo_id == photo_id,
                MealTag.tagged_user_id == recipient_id,
            )
        )
    ).scalar_one()
    assert existing.status == "declined"

    dup = MealTag(
        source_photo_id=photo_id,
        source_meal_id=(await async_db.get(Photo, photo_id)).meal_id,
        tagger_id=tagger_id,
        tagged_user_id=recipient_id,
        status="pending_analysis",
        source_date=DAY,
    )
    async_db.add(dup)
    with pytest.raises(IntegrityError):
        await async_db.commit()
    await async_db.rollback()


async def test_unconnected_handle_400(async_db: AsyncSession, storage: None):
    a = await _signup_client(async_db, uuid.uuid4().hex[:6])
    await _signup_client(async_db, uuid.uuid4().hex[:6])
    stranger = await _signup_client(async_db, uuid.uuid4().hex[:6])
    stranger_handle = (await stranger.get("/api/v1/auth/me")).json()["handle"]
    await _ensure_entry(a)
    resp = await a.post(
        f"/api/v1/entries/{DAY.isoformat()}/photos",
        files={"file": ("x.jpg", _jpg_bytes(), "image/jpeg")},
        data={"tagged_handles": json.dumps([stranger_handle])},
    )
    assert resp.status_code == 400


async def test_self_tag_400(async_db: AsyncSession, storage: None):
    client = await _signup_client(async_db, uuid.uuid4().hex[:6])
    handle = (await client.get("/api/v1/auth/me")).json()["handle"]
    await _ensure_entry(client)
    resp = await client.post(
        f"/api/v1/entries/{DAY.isoformat()}/photos",
        files={"file": ("x.jpg", _jpg_bytes(), "image/jpeg")},
        data={"tagged_handles": json.dumps([handle])},
    )
    assert resp.status_code == 400


async def test_max_tags_400(async_db: AsyncSession, storage: None):
    tagger = await _signup_client(async_db, uuid.uuid4().hex[:6])
    handles = []
    for i in range(11):
        peer = await _signup_client(async_db, f"p{i}")
        await _connect_users(tagger, peer)
        handles.append((await peer.get("/api/v1/auth/me")).json()["handle"])
    await _ensure_entry(tagger)
    resp = await tagger.post(
        f"/api/v1/entries/{DAY.isoformat()}/photos",
        files={"file": ("x.jpg", _jpg_bytes(), "image/jpeg")},
        data={"tagged_handles": json.dumps(handles)},
    )
    assert resp.status_code == 400


async def test_cancel_by_tagger(async_db: AsyncSession, storage: None):
    a = await _signup_client(async_db, uuid.uuid4().hex[:6])
    b = await _signup_client(async_db, uuid.uuid4().hex[:6])
    await _connect_users(a, b)
    b_handle = (await b.get("/api/v1/auth/me")).json()["handle"]
    await _upload_tagged(a, handles=[b_handle])
    tag_id = (await a.get("/api/v1/social/meal-tags")).json()["outgoing"][0]["id"]
    cancelled = await a.delete(f"/api/v1/social/meal-tags/{tag_id}")
    assert cancelled.status_code == 204
    assert (await a.get("/api/v1/social/meal-tags")).json()["outgoing"][0]["status"] == "cancelled"


async def test_retag_after_cancel(async_db: AsyncSession, storage: None):
    a = await _signup_client(async_db, uuid.uuid4().hex[:6])
    b = await _signup_client(async_db, uuid.uuid4().hex[:6])
    await _connect_users(a, b)
    b_handle = (await b.get("/api/v1/auth/me")).json()["handle"]
    photo_id = await _upload_tagged(a, handles=[b_handle])

    tag_id = (await a.get("/api/v1/social/meal-tags")).json()["outgoing"][0]["id"]
    cancelled = await a.delete(f"/api/v1/social/meal-tags/{tag_id}")
    assert cancelled.status_code == 204

    listed = await a.get(f"/api/v1/photos/{photo_id}/tags")
    assert listed.status_code == 200
    assert listed.json()["tags"] == []

    retagged = await a.post(f"/api/v1/photos/{photo_id}/tags", json={"handles": [b_handle]})
    assert retagged.status_code == 200, retagged.text
    assert len(retagged.json()["tags"]) == 1
    assert retagged.json()["tags"][0]["user"]["handle"] == b_handle
    assert retagged.json()["tags"][0]["id"] == tag_id
    assert retagged.json()["tags"][0]["status"] in ("pending_analysis", "pending_approval")


async def test_connection_removal_cancels_pending(
    async_db: AsyncSession, deferred_tag_storage: None
):
    a = await _signup_client(async_db, uuid.uuid4().hex[:6])
    b = await _signup_client(async_db, uuid.uuid4().hex[:6])
    conn_id = await _connect_users(a, b)
    b_handle = (await b.get("/api/v1/auth/me")).json()["handle"]
    photo_id = await _upload_tagged(a, handles=[b_handle])
    tagger_id = await _user_id(a)

    await _seed_confirmed_analysis(async_db, photo_id, tagger_id)
    await deliver_tags_for_source_background(photo_id, tagger_id)
    tag_id = (await b.get("/api/v1/social/meal-tags")).json()["incoming_pending"][0]["id"]
    await b.post(f"/api/v1/social/meal-tags/{tag_id}/approve")
    assert await _recipient_photo_count_http(b, DAY) == 1

    pending_photo = await _upload_tagged(a, handles=[b_handle])
    assert pending_photo
    outgoing = (await a.get("/api/v1/social/meal-tags")).json()["outgoing"]
    pending_tag = next(t for t in outgoing if t["status"] == "pending_approval")
    assert pending_tag is not None

    deleted = await a.delete(f"/api/v1/social/connections/{conn_id}")
    assert deleted.status_code == 204
    assert await _recipient_photo_count_http(b, DAY) == 1
    refreshed = (await a.get("/api/v1/social/meal-tags")).json()["outgoing"]
    cancelled = next(t for t in refreshed if t["id"] == pending_tag["id"])
    assert cancelled["status"] == "cancelled"


async def test_idempotent_delivery(async_db: AsyncSession, storage: None):
    a = await _signup_client(async_db, uuid.uuid4().hex[:6])
    b = await _signup_client(async_db, uuid.uuid4().hex[:6])
    await _connect_users(a, b)
    b_handle = (await b.get("/api/v1/auth/me")).json()["handle"]
    await b.put("/api/v1/settings/tagged-meal-mode", json={"tagged_meal_mode": "auto"})

    photo_id = await _upload_tagged(a, handles=[b_handle])
    tagger_id = await _user_id(a)
    await _seed_confirmed_analysis(async_db, photo_id, tagger_id)
    await deliver_tags_for_source_background(photo_id, tagger_id)
    await deliver_tags_for_source_background(photo_id, tagger_id)
    assert await _recipient_photo_count_http(b, DAY) == 1


async def test_photo_only_immediate_delivery(async_db: AsyncSession, storage: None):
    a = await _signup_client(async_db, uuid.uuid4().hex[:6])
    b = await _signup_client(async_db, uuid.uuid4().hex[:6])
    await _connect_users(a, b)
    b_handle = (await b.get("/api/v1/auth/me")).json()["handle"]
    await b.put("/api/v1/settings/tagged-meal-mode", json={"tagged_meal_mode": "auto"})

    await _upload_tagged(a, handles=[b_handle])
    assert await _recipient_photo_count_http(b, DAY) == 1


async def test_settings_mode_persists_and_validates(
    async_db: AsyncSession, patch_tag_delivery_maker: None
):
    client = await _signup_client(async_db, uuid.uuid4().hex[:6])
    updated = await client.put(
        "/api/v1/settings/tagged-meal-mode", json={"tagged_meal_mode": "auto"}
    )
    assert updated.status_code == 200
    assert updated.json()["tagged_meal_mode"] == "auto"
    got = await client.get("/api/v1/settings")
    assert got.json()["tagged_meal_mode"] == "auto"
    bad = await client.put("/api/v1/settings/tagged-meal-mode", json={"tagged_meal_mode": "nope"})
    assert bad.status_code == 422


async def test_recipient_edit_updates_shared_analysis(
    async_db: AsyncSession, deferred_tag_storage: None
):
    """Shared meal: ingredient edits on a copy are visible on the tagger's analysis."""
    a = await _signup_client(async_db, uuid.uuid4().hex[:6])
    b = await _signup_client(async_db, uuid.uuid4().hex[:6])
    await _connect_users(a, b)
    b_handle = (await b.get("/api/v1/auth/me")).json()["handle"]
    await b.put("/api/v1/settings/tagged-meal-mode", json={"tagged_meal_mode": "auto"})

    photo_id = await _upload_tagged(a, handles=[b_handle])
    tagger_id = await _user_id(a)
    await _seed_confirmed_analysis(async_db, photo_id, tagger_id)
    await deliver_tags_for_source_background(photo_id, tagger_id)

    entry = await b.get(f"/api/v1/entries/{DAY.isoformat()}")
    copy_photo_id = entry.json()["photos"][0]["id"]
    analysis = await b.get(f"/api/v1/photos/{copy_photo_id}/analysis")
    assert analysis.status_code == 200
    ingredient_id = analysis.json()["ingredients"][0]["id"]
    await b.put(f"/api/v1/ingredients/{ingredient_id}", json={"name": "edited-on-copy"})

    source_analysis = await a.get(f"/api/v1/photos/{photo_id}/analysis")
    assert source_analysis.status_code == 200
    assert source_analysis.json()["ingredients"][0]["name"] == "edited-on-copy"


async def _upload_plain(client: AsyncClient, day: datetime.date = DAY) -> int:
    await _ensure_entry(client, day)
    files = {"file": ("meal.jpg", _jpg_bytes(), "image/jpeg")}
    resp = await client.post(
        f"/api/v1/entries/{day.isoformat()}/photos",
        files=files,
        data={"label": "Dinner"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def test_recipient_sees_complete_analysis_before_tagger_confirms(
    async_db: AsyncSession, deferred_tag_storage: None
):
    a = await _signup_client(async_db, uuid.uuid4().hex[:6])
    b = await _signup_client(async_db, uuid.uuid4().hex[:6])
    await _connect_users(a, b)
    b_handle = (await b.get("/api/v1/auth/me")).json()["handle"]
    await b.put("/api/v1/settings/tagged-meal-mode", json={"tagged_meal_mode": "auto"})

    photo_id = await _upload_tagged(a, handles=[b_handle])
    tagger_id = await _user_id(a)
    await apply_session_user_id(async_db, tagger_id)
    analysis = PhotoAnalysis(
        user_id=tagger_id,
        photo_id=photo_id,
        status="complete",
        dish_name="Shared pasta",
        cuisine="italian",
        dish_confidence=0.85,
    )
    async_db.add(analysis)
    await async_db.commit()

    entry = await b.get(f"/api/v1/entries/{DAY.isoformat()}")
    copy_photo_id = entry.json()["photos"][0]["id"]
    resp = await b.get(f"/api/v1/photos/{copy_photo_id}/analysis")
    assert resp.status_code == 200
    assert resp.json()["dish_name"] == "Shared pasta"
    assert resp.json()["status"] == "complete"


async def test_linked_confirm_visible_to_all_participants(
    async_db: AsyncSession, deferred_tag_storage: None
):
    a = await _signup_client(async_db, uuid.uuid4().hex[:6])
    b = await _signup_client(async_db, uuid.uuid4().hex[:6])
    await _connect_users(a, b)
    b_handle = (await b.get("/api/v1/auth/me")).json()["handle"]
    await b.put("/api/v1/settings/tagged-meal-mode", json={"tagged_meal_mode": "auto"})

    photo_id = await _upload_tagged(a, handles=[b_handle])
    tagger_id = await _user_id(a)
    await _seed_confirmed_analysis(async_db, photo_id, tagger_id)
    await deliver_tags_for_source_background(photo_id, tagger_id)

    entry = await b.get(f"/api/v1/entries/{DAY.isoformat()}")
    copy_photo_id = entry.json()["photos"][0]["id"]
    confirmed = await a.put(f"/api/v1/photos/{photo_id}/analysis/confirm", json={})
    assert confirmed.status_code == 200

    copy_analysis = await b.get(f"/api/v1/photos/{copy_photo_id}/analysis")
    assert copy_analysis.json()["status"] == "confirmed"


async def test_recipient_confirm_updates_shared_meal(
    async_db: AsyncSession, deferred_tag_storage: None
):
    a = await _signup_client(async_db, uuid.uuid4().hex[:6])
    b = await _signup_client(async_db, uuid.uuid4().hex[:6])
    await _connect_users(a, b)
    b_handle = (await b.get("/api/v1/auth/me")).json()["handle"]
    await b.put("/api/v1/settings/tagged-meal-mode", json={"tagged_meal_mode": "auto"})

    photo_id = await _upload_tagged(a, handles=[b_handle])
    tagger_id = await _user_id(a)
    await apply_session_user_id(async_db, tagger_id)
    analysis = PhotoAnalysis(
        user_id=tagger_id,
        photo_id=photo_id,
        status="needs_review",
        dish_name="Salad",
        dish_confidence=0.6,
    )
    async_db.add(analysis)
    await async_db.commit()
    await deliver_tags_for_source_background(photo_id, tagger_id)

    entry = await b.get(f"/api/v1/entries/{DAY.isoformat()}")
    copy_photo_id = entry.json()["photos"][0]["id"]
    confirmed = await b.put(f"/api/v1/photos/{copy_photo_id}/analysis/confirm", json={})
    assert confirmed.status_code == 200

    source = await a.get(f"/api/v1/photos/{photo_id}/analysis")
    assert source.json()["status"] == "confirmed"


async def test_approve_mode_placement_shares_meal_id(
    async_db: AsyncSession, deferred_tag_storage: None
):
    a = await _signup_client(async_db, uuid.uuid4().hex[:6])
    b = await _signup_client(async_db, uuid.uuid4().hex[:6])
    await _connect_users(a, b)
    b_handle = (await b.get("/api/v1/auth/me")).json()["handle"]

    photo_id = await _upload_tagged(a, handles=[b_handle])
    tagger_id = await _user_id(a)
    await _seed_confirmed_analysis(async_db, photo_id, tagger_id)
    await deliver_tags_for_source_background(photo_id, tagger_id)

    tag_id = (await b.get("/api/v1/social/meal-tags")).json()["incoming_pending"][0]["id"]
    await b.post(f"/api/v1/social/meal-tags/{tag_id}/approve")

    await apply_session_user_id(async_db, tagger_id)
    source = await async_db.get(Photo, photo_id)
    copy = (
        await async_db.execute(select(Photo).where(Photo.source_photo_id == photo_id))
    ).scalar_one()
    assert copy.meal_id == source.meal_id


async def test_retroactive_photo_tags(async_db: AsyncSession, storage: None):
    a = await _signup_client(async_db, uuid.uuid4().hex[:6])
    b = await _signup_client(async_db, uuid.uuid4().hex[:6])
    await _connect_users(a, b)
    b_handle = (await b.get("/api/v1/auth/me")).json()["handle"]
    photo_id = await _upload_plain(a)

    tagged = await a.post(f"/api/v1/photos/{photo_id}/tags", json={"handles": [b_handle]})
    assert tagged.status_code == 200, tagged.text
    assert len(tagged.json()["tags"]) == 1

    listed = await a.get(f"/api/v1/photos/{photo_id}/tags")
    assert listed.status_code == 200
    assert listed.json()["tags"][0]["user"]["handle"] == b_handle

    entry = await a.get(f"/api/v1/entries/{DAY.isoformat()}")
    assert entry.status_code == 200
    photo = next(p for p in entry.json()["photos"] if p["id"] == photo_id)
    assert b_handle in photo["tagged_with_handles"]

    duplicate = await a.post(f"/api/v1/photos/{photo_id}/tags", json={"handles": [b_handle]})
    assert duplicate.status_code == 200
    assert len(duplicate.json()["tags"]) == 1


# ---------------------------------------------------------------------------
# GET /api/v1/photos — profile-grid list endpoint (issue #363)
# ---------------------------------------------------------------------------


async def test_photos_list_order_pagination_and_isolation(async_db: AsyncSession, storage: None):
    a = await _signup_client(async_db, uuid.uuid4().hex[:6])
    b = await _signup_client(async_db, uuid.uuid4().hex[:6])
    first = await _upload_plain(a)
    second = await _upload_plain(a)
    intruder = await _upload_plain(b)

    listed = (await a.get("/api/v1/photos")).json()
    assert [p["id"] for p in listed] == [second, first]
    assert intruder not in {p["id"] for p in listed}

    limited = (await a.get("/api/v1/photos?limit=1")).json()
    assert [p["id"] for p in limited] == [second]
    shifted = (await a.get("/api/v1/photos?limit=1&offset=1")).json()
    assert [p["id"] for p in shifted] == [first]


async def test_photos_list_tagged_scope(async_db: AsyncSession, storage: None):
    a = await _signup_client(async_db, uuid.uuid4().hex[:6])
    b = await _signup_client(async_db, uuid.uuid4().hex[:6])
    await _connect_users(a, b)
    a_handle = (await a.get("/api/v1/auth/me")).json()["handle"]
    b_handle = (await b.get("/api/v1/auth/me")).json()["handle"]
    await b.put("/api/v1/settings/tagged-meal-mode", json={"tagged_meal_mode": "auto"})

    await _upload_plain(b)
    source_id = await _upload_tagged(a, handles=[b_handle])

    all_scope = (await b.get("/api/v1/photos")).json()
    assert len(all_scope) == 2

    tagged = (await b.get("/api/v1/photos?scope=tagged")).json()
    assert len(tagged) == 1
    assert tagged[0]["tagged_by_handle"] == a_handle
    assert tagged[0]["source_photo_id"] == source_id

    # The tagger's own photos are never "tagged" copies...
    assert (await a.get("/api/v1/photos?scope=tagged")).json() == []
    # ...but the source photo carries the companion handles.
    a_all = (await a.get("/api/v1/photos")).json()
    source = next(p for p in a_all if p["id"] == source_id)
    assert source["tagged_with_handles"] == [b_handle]


async def test_photos_list_rejects_bad_params(
    async_db: AsyncSession, patch_tag_delivery_maker: None
):
    client = await _signup_client(async_db, uuid.uuid4().hex[:6])
    assert (await client.get("/api/v1/photos?scope=mine")).status_code == 422
    assert (await client.get("/api/v1/photos?limit=0")).status_code == 422
