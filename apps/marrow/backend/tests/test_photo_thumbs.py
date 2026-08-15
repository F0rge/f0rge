"""Tests for photo thumbnail storage and GET /photos/{id}/thumb."""

from __future__ import annotations

import datetime
import io
import os
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
from app.services.food_analysis_orchestrator import FoodAnalysisOrchestrator
from app.services.meal_tags import MealTagService
from app.services.photo_storage import thumb_filename
from app.services.photos import PHOTO_CACHE_CONTROL, PhotoService

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def authed_user_id(authed_client: AsyncClient) -> uuid.UUID:
    resp = await authed_client.get("/api/v1/auth/me")
    assert resp.status_code == 200
    return uuid.UUID(resp.json()["user_id"])


@pytest_asyncio.fixture
async def isolated_storage(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    photo_dir = tmp_path / "photos"
    photo_dir.mkdir()
    monkeypatch.setattr(settings, "photo_dir", str(photo_dir))
    monkeypatch.setattr(settings, "food_analysis_enabled", False)
    monkeypatch.setattr(settings, "openrouter_api_key", "")


def _png_bytes() -> bytes:
    img = Image.new("RGB", (800, 600), color="blue")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


async def _make_entry(db: AsyncSession, day: datetime.date, user_id: uuid.UUID) -> Entry:
    await apply_session_user_id(db, user_id)
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
    db: AsyncSession,
    day: datetime.date,
    user_id: uuid.UUID,
):
    token = user_id_ctx.set(user_id)
    try:
        upload = UploadFile(filename="meal.png", file=io.BytesIO(_png_bytes()))
        service = PhotoService(db, FoodAnalysisOrchestrator(), MealTagService(db))
        return await service.upload(
            entry_date=day,
            file=upload,
            label=None,
            meal_time=None,
            background_tasks=BackgroundTasks(),
        )
    finally:
        user_id_ctx.reset(token)


async def test_thumb_filename_naming() -> None:
    assert thumb_filename("2026-08-04_photo-1.jpg") == "2026-08-04_photo-1_thumb.jpg"


async def test_upload_creates_thumb_on_disk(
    async_db: AsyncSession,
    authed_user_id: uuid.UUID,
    isolated_storage: None,
) -> None:
    day = datetime.date(2026, 8, 4)
    await _make_entry(async_db, day, authed_user_id)
    photo = await _upload(async_db, day, authed_user_id)
    thumb_path = os.path.join(settings.photo_dir, thumb_filename(photo.filename))
    full_path = os.path.join(settings.photo_dir, photo.filename)

    assert os.path.exists(full_path)
    assert os.path.exists(thumb_path)


async def test_get_thumb_returns_200_with_cache_header(
    async_db: AsyncSession,
    authed_client: AsyncClient,
    authed_user_id: uuid.UUID,
    isolated_storage: None,
) -> None:
    day = datetime.date(2026, 8, 4)
    await _make_entry(async_db, day, authed_user_id)
    photo = await _upload(async_db, day, authed_user_id)

    resp = await authed_client.get(f"/api/v1/photos/{photo.id}/thumb")
    assert resp.status_code == 200
    assert resp.headers.get("cache-control") == PHOTO_CACHE_CONTROL
    assert resp.headers.get("content-type", "").startswith("image/jpeg")


async def test_get_file_includes_cache_header(
    async_db: AsyncSession,
    authed_client: AsyncClient,
    authed_user_id: uuid.UUID,
    isolated_storage: None,
) -> None:
    day = datetime.date(2026, 8, 4)
    await _make_entry(async_db, day, authed_user_id)
    photo = await _upload(async_db, day, authed_user_id)

    resp = await authed_client.get(f"/api/v1/photos/{photo.id}/file")
    assert resp.status_code == 200
    assert resp.headers.get("cache-control") == PHOTO_CACHE_CONTROL


async def test_missing_thumb_lazy_generates(
    async_db: AsyncSession,
    authed_client: AsyncClient,
    authed_user_id: uuid.UUID,
    isolated_storage: None,
) -> None:
    day = datetime.date(2026, 8, 4)
    await _make_entry(async_db, day, authed_user_id)
    photo = await _upload(async_db, day, authed_user_id)

    thumb_path = os.path.join(settings.photo_dir, thumb_filename(photo.filename))
    os.remove(thumb_path)
    assert not os.path.exists(thumb_path)

    resp = await authed_client.get(f"/api/v1/photos/{photo.id}/thumb")
    assert resp.status_code == 200
    assert os.path.exists(thumb_path)


async def test_thumb_not_found_for_other_users_photo(
    authed_client: AsyncClient,
) -> None:
    resp = await authed_client.get("/api/v1/photos/999999/thumb")
    assert resp.status_code == 404


async def test_delete_removes_thumb(
    async_db: AsyncSession,
    authed_client: AsyncClient,
    authed_user_id: uuid.UUID,
    isolated_storage: None,
) -> None:
    day = datetime.date(2026, 8, 4)
    await _make_entry(async_db, day, authed_user_id)
    photo = await _upload(async_db, day, authed_user_id)

    full_path = os.path.join(settings.photo_dir, photo.filename)
    thumb_path = os.path.join(settings.photo_dir, thumb_filename(photo.filename))
    assert os.path.exists(full_path)
    assert os.path.exists(thumb_path)

    resp = await authed_client.delete(f"/api/v1/photos/{photo.id}")
    assert resp.status_code == 204
    assert not os.path.exists(full_path)
    assert not os.path.exists(thumb_path)


async def test_remote_serve_presigns_without_head_storm(
    async_db: AsyncSession,
    authed_client: AsyncClient,
    authed_user_id: uuid.UUID,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GET /file is HEAD-free; GET /thumb does at most one canonical HEAD."""
    from app.models.meal import Meal
    from app.models.photo import Photo
    from app.services import object_storage

    monkeypatch.setattr(settings, "bucket_name", "test-bucket")
    monkeypatch.setattr(settings, "aws_access_key_id", "test-key")
    monkeypatch.setattr(settings, "aws_secret_access_key", "test-secret")
    monkeypatch.setattr(settings, "aws_endpoint_url_s3", "http://storage.test")
    monkeypatch.setattr(settings, "food_analysis_enabled", False)

    head_calls: list[str] = []

    class _StubS3:
        def head_object(self, Bucket: str, Key: str) -> dict:  # noqa: N803
            head_calls.append(Key)
            return {}

        def generate_presigned_url(
            self,
            ClientMethod: str,
            Params: dict,
            ExpiresIn: int,  # noqa: N803
        ) -> str:
            return f"https://storage.test/{Params['Bucket']}/{Params['Key']}?e={ExpiresIn}"

    monkeypatch.setattr(object_storage, "_s3_client", lambda: _StubS3())

    day = datetime.date(2026, 8, 4)
    entry = await _make_entry(async_db, day, authed_user_id)
    filename = "2026-08-04_photo-1.jpg"
    now = datetime.datetime.utcnow()
    meal = Meal(
        owner_user_id=authed_user_id,
        filename=filename,
        original_filename="meal.png",
        meal_time=now,
        created_at=now,
    )
    async_db.add(meal)
    await async_db.flush()
    photo = Photo(
        user_id=authed_user_id,
        entry_id=entry.id,
        meal_id=meal.id,
        filename=filename,
        original_filename="meal.png",
        meal_time=now,
        created_at=now,
    )
    async_db.add(photo)
    await async_db.commit()
    await async_db.refresh(photo)

    head_calls.clear()
    file_resp = await authed_client.get(f"/api/v1/photos/{photo.id}/file", follow_redirects=False)
    assert file_resp.status_code == 307
    assert file_resp.headers.get("cache-control") == PHOTO_CACHE_CONTROL
    assert f"{authed_user_id}/{filename}" in file_resp.headers.get("location", "")
    assert head_calls == []

    head_calls.clear()
    thumb_resp = await authed_client.get(f"/api/v1/photos/{photo.id}/thumb", follow_redirects=False)
    assert thumb_resp.status_code == 307
    assert thumb_resp.headers.get("cache-control") == PHOTO_CACHE_CONTROL
    assert thumb_filename(filename) in thumb_resp.headers.get("location", "")
    # One canonical HEAD for "does thumb exist?" — no multi-layout probe.
    assert len(head_calls) == 1
    assert head_calls[0] == f"{authed_user_id}/{thumb_filename(filename)}"
