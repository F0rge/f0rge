"""Tests for PATCH /api/v1/photos/{photo_id} label support.

Exercises the real seams: a temporary on-disk photo dir, the real
``PhotoService.upload`` collaborators, and a real PIN-login round-trip for the
HTTP endpoint. Nothing under test is mocked (per feedback_no_mocks_at_seam_under_test.md).

Covers:
- label-only PATCH sets label, preserves meal_time
- ""/whitespace label PATCH clears label to NULL
- meal_time-only PATCH preserves label
- 404 on a missing photo
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
from app.config import settings
from app.models.entry import Entry
from app.services.food_analysis_orchestrator import FoodAnalysisOrchestrator
from app.services.photos import PhotoService


@pytest_asyncio.fixture
async def authed_user_id(authed_client: AsyncClient) -> uuid.UUID:
    resp = await authed_client.get("/api/v1/auth/me")
    assert resp.status_code == 200
    return uuid.UUID(resp.json()["user_id"])


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def isolated_storage(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    photo_dir = tmp_path / "photos"
    photo_dir.mkdir()
    monkeypatch.setattr(settings, "photo_dir", str(photo_dir))
    monkeypatch.setattr(settings, "food_analysis_enabled", False)
    monkeypatch.setattr(settings, "openrouter_api_key", "")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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
        service = PhotoService(db, FoodAnalysisOrchestrator())
        return await service.upload(
            entry_date=day,
            file=upload,
            label=label,
            meal_time=None,
            background_tasks=BackgroundTasks(),
        )
    finally:
        user_id_ctx.reset(token)


# ---------------------------------------------------------------------------
# PATCH /api/v1/photos/{photo_id}
# ---------------------------------------------------------------------------


async def test_patch_label_only_sets_label_preserves_meal_time(
    authed_client: AsyncClient,
    async_db: AsyncSession,
    isolated_storage: None,
    authed_user_id: uuid.UUID,
) -> None:
    day = datetime.date(2026, 6, 1)
    await _make_entry(async_db, day, authed_user_id)
    photo = await _upload(async_db, day, authed_user_id)
    original_meal_time = photo.meal_time

    resp = await authed_client.patch(f"/api/v1/photos/{photo.id}", json={"label": "Leftover pasta"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["label"] == "Leftover pasta"
    assert body["meal_time"] == original_meal_time.isoformat()


@pytest.mark.parametrize("blank_label", ["", "   "])
async def test_patch_blank_label_clears_to_null(
    authed_client: AsyncClient,
    async_db: AsyncSession,
    isolated_storage: None,
    blank_label: str,
    authed_user_id: uuid.UUID,
) -> None:
    day = datetime.date(2026, 6, 2)
    await _make_entry(async_db, day, authed_user_id)
    photo = await _upload(async_db, day, authed_user_id, label="Original label")

    resp = await authed_client.patch(f"/api/v1/photos/{photo.id}", json={"label": blank_label})

    assert resp.status_code == 200
    assert resp.json()["label"] is None


async def test_patch_meal_time_only_preserves_label(
    authed_client: AsyncClient,
    async_db: AsyncSession,
    isolated_storage: None,
    authed_user_id: uuid.UUID,
) -> None:
    day = datetime.date(2026, 6, 3)
    await _make_entry(async_db, day, authed_user_id)
    photo = await _upload(async_db, day, authed_user_id, label="Kept label")

    new_time = datetime.datetime(2026, 6, 3, 13, 24, 0)
    resp = await authed_client.patch(
        f"/api/v1/photos/{photo.id}", json={"meal_time": new_time.isoformat()}
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["label"] == "Kept label"
    assert body["meal_time"] == new_time.isoformat()


async def test_patch_missing_photo_returns_404(authed_client: AsyncClient) -> None:
    resp = await authed_client.patch("/api/v1/photos/99999", json={"label": "Nope"})

    assert resp.status_code == 404
