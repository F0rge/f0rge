"""Tests for profile photo visibility (issue #403).

Covers:
- hide/unhide via PATCH /photos/{id} + visibility filters on GET /photos
- explicit per-photo diet tags: set/replace/clear, unknown key rejected,
  fresh-signup RLS ownership guard
- profile tag-filter rule matrix (off/hide/show_only x derived/suppressed/explicit)
- PUT /settings/profile-tag-filter persistence + validation
- partner-copy independence (hiding a source row leaves the copy visible)
"""

from __future__ import annotations

import datetime
import io
import uuid

import pytest
import pytest_asyncio
from fastapi import BackgroundTasks, UploadFile
from httpx import AsyncClient
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession

from f0rge_db.auth_context import user_id_ctx
from f0rge_db.tenant import apply_session_user_id
from app.config import settings
from app.models.entry import Entry
from app.models.photo import Photo
from app.models.photo_analysis import PhotoAnalysis
from app.models.photo_ingredient import PhotoIngredient
from app.models.user import LEO_PLACEHOLDER_PASSWORD_HASH, User
from app.schemas.photo import PhotoUpdate
from app.services.food_analysis_orchestrator import FoodAnalysisOrchestrator
from app.services.meal_tags import MealTagService
from app.services.photos import PhotoService
from tests.conftest import authed_user_id as fetch_authed_user_id

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Fixtures + helpers (pattern from test_photos_update_label.py)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def authed_user_id(authed_client: AsyncClient) -> uuid.UUID:
    return await fetch_authed_user_id(authed_client)


@pytest_asyncio.fixture
async def isolated_storage(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    photo_dir = tmp_path / "photos"
    photo_dir.mkdir()
    monkeypatch.setattr(settings, "photo_dir", str(photo_dir))
    monkeypatch.setattr(settings, "food_analysis_enabled", False)
    monkeypatch.setattr(settings, "openrouter_api_key", "")


def _jpg_bytes() -> bytes:
    img = Image.new("RGB", (10, 10), color="green")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


async def _make_entry(db: AsyncSession, day: datetime.date, user_id: uuid.UUID) -> Entry:
    entry = Entry(
        user_id=user_id,
        date=day,
        overall=2,
        bloating=0,
        stool_normal=True,
        joint_pain=0,
        neuro=0,
        sleep_quality=2,
        stress=1,
        diet_risk="normal",
        supplements="",
        sick=False,
        hot_shower=False,
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry


async def _upload(
    db: AsyncSession, day: datetime.date, user_id: uuid.UUID, label: str | None = None
):
    token = user_id_ctx.set(user_id)
    try:
        upload = UploadFile(filename="meal.jpg", file=io.BytesIO(_jpg_bytes()))
        service = PhotoService(db, FoodAnalysisOrchestrator(), MealTagService(db))
        return await service.upload(
            entry_date=day,
            file=upload,
            label=label,
            meal_time=None,
            background_tasks=BackgroundTasks(),
        )
    finally:
        user_id_ctx.reset(token)


async def _seed_confirmed_gluten_analysis(
    db: AsyncSession, photo_id: int, user_id: uuid.UUID
) -> PhotoAnalysis:
    """Confirmed analysis with one contains_gluten ingredient -> derived 'gluten'."""
    await apply_session_user_id(db, user_id)
    analysis = PhotoAnalysis(
        user_id=user_id,
        photo_id=photo_id,
        status="confirmed",
        dish_name="Toast",
        dish_confidence=0.9,
    )
    db.add(analysis)
    await db.flush()
    db.add(
        PhotoIngredient(
            user_id=user_id,
            analysis_id=analysis.id,
            name="bread",
            confidence=0.9,
            contains_gluten=True,
        )
    )
    await db.commit()
    return analysis


async def _photo_ids(client: AsyncClient, **params) -> list[int]:
    resp = await client.get("/api/v1/photos", params=params)
    assert resp.status_code == 200, resp.text
    return [p["id"] for p in resp.json()]


# ---------------------------------------------------------------------------
# Hide / unhide
# ---------------------------------------------------------------------------


async def test_hide_unhide_flow(
    authed_client: AsyncClient,
    async_db: AsyncSession,
    isolated_storage: None,
    authed_user_id: uuid.UUID,
) -> None:
    day = datetime.date(2026, 7, 1)
    await _make_entry(async_db, day, authed_user_id)
    photo_a = await _upload(async_db, day, authed_user_id, label="A")
    photo_b = await _upload(async_db, day, authed_user_id, label="B")

    resp = await authed_client.patch(f"/api/v1/photos/{photo_a.id}", json={"hidden": True})
    assert resp.status_code == 200
    assert resp.json()["hidden_at"] is not None

    assert await _photo_ids(authed_client) == [photo_b.id]
    assert await _photo_ids(authed_client, visibility="hidden") == [photo_a.id]
    assert set(await _photo_ids(authed_client, visibility="all")) == {photo_a.id, photo_b.id}

    # Check-in entry payload is unaffected by hiding.
    entry_resp = await authed_client.get(f"/api/v1/entries/{day.isoformat()}")
    assert entry_resp.status_code == 200
    entry_photo_ids = {p["id"] for p in entry_resp.json()["photos"]}
    assert entry_photo_ids == {photo_a.id, photo_b.id}

    resp = await authed_client.patch(f"/api/v1/photos/{photo_a.id}", json={"hidden": False})
    assert resp.status_code == 200
    assert resp.json()["hidden_at"] is None
    assert set(await _photo_ids(authed_client)) == {photo_a.id, photo_b.id}


# ---------------------------------------------------------------------------
# Explicit diet tags
# ---------------------------------------------------------------------------


async def test_diet_tags_set_replace_clear(
    authed_client: AsyncClient,
    async_db: AsyncSession,
    isolated_storage: None,
    authed_user_id: uuid.UUID,
) -> None:
    day = datetime.date(2026, 7, 2)
    await _make_entry(async_db, day, authed_user_id)
    photo = await _upload(async_db, day, authed_user_id)

    resp = await authed_client.patch(
        f"/api/v1/photos/{photo.id}", json={"diet_tags": ["gluten", "dairy"]}
    )
    assert resp.status_code == 200
    assert resp.json()["diet_tags"] == ["dairy", "gluten"]

    resp = await authed_client.patch(
        f"/api/v1/photos/{photo.id}", json={"diet_tags": ["high-fodmap"]}
    )
    assert resp.status_code == 200
    assert resp.json()["diet_tags"] == ["high-fodmap"]

    resp = await authed_client.patch(f"/api/v1/photos/{photo.id}", json={"diet_tags": []})
    assert resp.status_code == 200
    assert resp.json()["diet_tags"] == []


async def test_diet_tags_unknown_key_rejected(
    authed_client: AsyncClient,
    async_db: AsyncSession,
    isolated_storage: None,
    authed_user_id: uuid.UUID,
) -> None:
    day = datetime.date(2026, 7, 3)
    await _make_entry(async_db, day, authed_user_id)
    photo = await _upload(async_db, day, authed_user_id)

    resp = await authed_client.patch(
        f"/api/v1/photos/{photo.id}", json={"diet_tags": ["not-a-tag"]}
    )
    assert resp.status_code == 400
    assert "not-a-tag" in resp.json()["detail"]


async def test_fresh_signup_user_sees_own_tags(
    authed_client: AsyncClient,
    async_db: AsyncSession,
    isolated_storage: None,
    authed_user_id: uuid.UUID,
) -> None:
    """RLS ownership guard (PR #359): tag rows must be owned by the signup user,
    not the default user, or this list comes back empty."""
    day = datetime.date(2026, 7, 4)
    await _make_entry(async_db, day, authed_user_id)
    photo = await _upload(async_db, day, authed_user_id)

    resp = await authed_client.patch(f"/api/v1/photos/{photo.id}", json={"diet_tags": ["dairy"]})
    assert resp.status_code == 200, resp.text

    listed = await authed_client.get("/api/v1/photos")
    assert listed.status_code == 200
    by_id = {p["id"]: p for p in listed.json()}
    assert by_id[photo.id]["diet_tags"] == ["dairy"]


# ---------------------------------------------------------------------------
# Profile tag-filter rule matrix
# ---------------------------------------------------------------------------


async def test_filter_rule_matrix(
    authed_client: AsyncClient,
    async_db: AsyncSession,
    isolated_storage: None,
    authed_user_id: uuid.UUID,
) -> None:
    day = datetime.date(2026, 7, 5)
    await _make_entry(async_db, day, authed_user_id)
    p_gluten = await _upload(async_db, day, authed_user_id, label="gluten-meal")
    p_custom = await _upload(async_db, day, authed_user_id, label="custom-meal")
    p_plain = await _upload(async_db, day, authed_user_id, label="plain-meal")
    all_ids = {p_gluten.id, p_custom.id, p_plain.id}

    analysis = await _seed_confirmed_gluten_analysis(async_db, p_gluten.id, authed_user_id)

    created = await authed_client.post(
        "/api/v1/diet-tags/catalog", json={"key": "keto", "label": "Keto"}
    )
    assert created.status_code == 201
    tagged = await authed_client.patch(
        f"/api/v1/photos/{p_custom.id}", json={"diet_tags": ["keto"]}
    )
    assert tagged.status_code == 200

    # mode off (default): everything visible, derived flag exposed.
    listed = await authed_client.get("/api/v1/photos")
    by_id = {p["id"]: p for p in listed.json()}
    assert set(by_id) == all_ids
    assert by_id[p_gluten.id]["derived_diet_tags"] == ["gluten"]
    assert by_id[p_custom.id]["diet_tags"] == ["keto"]

    # hide + gluten: derived-gluten photo drops out.
    resp = await authed_client.put(
        "/api/v1/settings/profile-tag-filter",
        json={"profile_tag_filter_mode": "hide", "profile_filter_tags": ["gluten"]},
    )
    assert resp.status_code == 200
    assert set(await _photo_ids(authed_client)) == {p_custom.id, p_plain.id}

    # Check-in entry payload ignores the profile rule.
    entry_resp = await authed_client.get(f"/api/v1/entries/{day.isoformat()}")
    assert {p["id"] for p in entry_resp.json()["photos"]} == all_ids

    # show_only + gluten: only the derived-gluten photo remains.
    await authed_client.put(
        "/api/v1/settings/profile-tag-filter",
        json={"profile_tag_filter_mode": "show_only", "profile_filter_tags": ["gluten"]},
    )
    assert await _photo_ids(authed_client) == [p_gluten.id]

    # show_only + explicit custom tag.
    await authed_client.put(
        "/api/v1/settings/profile-tag-filter",
        json={"profile_tag_filter_mode": "show_only", "profile_filter_tags": ["keto"]},
    )
    assert await _photo_ids(authed_client) == [p_custom.id]

    # gluten_free_confirmed suppresses the derived flag -> photo no longer matches.
    await apply_session_user_id(async_db, authed_user_id)
    analysis.gluten_free_confirmed = True
    await async_db.commit()

    await authed_client.put(
        "/api/v1/settings/profile-tag-filter",
        json={"profile_tag_filter_mode": "hide", "profile_filter_tags": ["gluten"]},
    )
    assert set(await _photo_ids(authed_client)) == all_ids
    await authed_client.put(
        "/api/v1/settings/profile-tag-filter",
        json={"profile_tag_filter_mode": "show_only", "profile_filter_tags": ["gluten"]},
    )
    assert await _photo_ids(authed_client) == []


async def test_hidden_listing_is_never_tag_filtered(
    authed_client: AsyncClient,
    async_db: AsyncSession,
    isolated_storage: None,
    authed_user_id: uuid.UUID,
) -> None:
    day = datetime.date(2026, 7, 6)
    await _make_entry(async_db, day, authed_user_id)
    photo = await _upload(async_db, day, authed_user_id)

    await authed_client.patch(
        f"/api/v1/photos/{photo.id}", json={"hidden": True, "diet_tags": ["gluten"]}
    )
    await authed_client.put(
        "/api/v1/settings/profile-tag-filter",
        json={"profile_tag_filter_mode": "hide", "profile_filter_tags": ["gluten"]},
    )
    assert await _photo_ids(authed_client, visibility="hidden") == [photo.id]


# ---------------------------------------------------------------------------
# Settings endpoint
# ---------------------------------------------------------------------------


async def test_profile_tag_filter_settings_roundtrip(authed_client: AsyncClient) -> None:
    initial = await authed_client.get("/api/v1/settings")
    assert initial.status_code == 200
    assert initial.json()["profile_tag_filter_mode"] == "off"
    assert initial.json()["profile_filter_tags"] == []

    resp = await authed_client.put(
        "/api/v1/settings/profile-tag-filter",
        json={"profile_tag_filter_mode": "hide", "profile_filter_tags": ["gluten", "dairy"]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["profile_tag_filter_mode"] == "hide"
    assert body["profile_filter_tags"] == ["gluten", "dairy"]

    fetched = await authed_client.get("/api/v1/settings")
    assert fetched.json()["profile_tag_filter_mode"] == "hide"
    assert fetched.json()["profile_filter_tags"] == ["gluten", "dairy"]


async def test_profile_tag_filter_invalid_mode_422(authed_client: AsyncClient) -> None:
    resp = await authed_client.put(
        "/api/v1/settings/profile-tag-filter",
        json={"profile_tag_filter_mode": "sometimes", "profile_filter_tags": []},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Partner-copy independence
# ---------------------------------------------------------------------------


async def test_hiding_source_leaves_partner_copy_visible(
    async_db: AsyncSession,
    isolated_storage: None,
) -> None:
    """hidden_at lives on the per-user photo row: hiding the source photo must
    not touch a delivered copy (different user_id, source_photo_id set)."""
    user_a = User(
        id=uuid.uuid4(),
        email="viz-a@example.com",
        password_hash=LEO_PLACEHOLDER_PASSWORD_HASH,
        handle="viz_a",
    )
    user_b = User(
        id=uuid.uuid4(),
        email="viz-b@example.com",
        password_hash=LEO_PLACEHOLDER_PASSWORD_HASH,
        handle="viz_b",
    )
    async_db.add_all([user_a, user_b])
    await async_db.commit()

    day = datetime.date(2026, 7, 7)
    await apply_session_user_id(async_db, user_a.id)
    await _make_entry(async_db, day, user_a.id)
    source = await _upload(async_db, day, user_a.id, label="source")

    await apply_session_user_id(async_db, user_b.id)
    entry_b = await _make_entry(async_db, day, user_b.id)
    copy = Photo(
        user_id=user_b.id,
        entry_id=entry_b.id,
        filename="copy.jpg",
        source_photo_id=source.id,
        tagged_by_user_id=user_a.id,
    )
    async_db.add(copy)
    await async_db.commit()

    # A hides the source photo.
    await apply_session_user_id(async_db, user_a.id)
    token = user_id_ctx.set(user_a.id)
    try:
        service = PhotoService(async_db, FoodAnalysisOrchestrator(), MealTagService(async_db))
        updated = await service.update_photo(source.id, PhotoUpdate(hidden=True))
        assert updated.hidden_at is not None
    finally:
        user_id_ctx.reset(token)

    # B's copy is untouched and still listed.
    await apply_session_user_id(async_db, user_b.id)
    token = user_id_ctx.set(user_b.id)
    try:
        service_b = PhotoService(async_db, FoodAnalysisOrchestrator(), MealTagService(async_db))
        listed = await service_b.list_photos("all", "visible", 24, 0)
        assert [p.id for p in listed] == [copy.id]
        assert listed[0].hidden_at is None
    finally:
        user_id_ctx.reset(token)
