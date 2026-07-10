"""Tests for meal_time on Photo and alcohol_units/caffeine_servings on Entry.

Covers:
- Upload without meal_time defaults to ~utcnow
- Upload with explicit meal_time persists it
- PATCH /photos/{photo_id} updates meal_time on an existing photo
- PATCH on a missing photo returns 404
- alcohol_units / caffeine_servings round-trip on Entry create and update

Two legacy ad-hoc migration-pattern tests were dropped — Alembic now owns
the schema lifecycle (see ``backend/migrations/``), so simulating a manual
``ALTER TABLE`` against the historical schema no longer represents the real
upgrade path.
"""

from __future__ import annotations

import datetime
import io
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from fastapi import BackgroundTasks, UploadFile
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.exceptions import NotFoundError
from app.models.entry import Entry
from app.models.photo import Photo
from app.schemas.photo import PhotoUpdate
from app.services.food_analysis_orchestrator import FoodAnalysisOrchestrator
from app.services.photos import PhotoService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def isolated_storage(tmp_path, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[None]:
    """Redirect photo storage to a temp dir."""
    photo_dir = tmp_path / "photos"
    photo_dir.mkdir()
    monkeypatch.setattr(settings, "photo_dir", str(photo_dir))
    monkeypatch.setattr(settings, "food_analysis_enabled", False)
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    yield


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _make_entry(db: AsyncSession, day: datetime.date) -> Entry:
    entry = Entry(
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


def _png_bytes() -> bytes:
    img = Image.new("RGB", (10, 10), color="blue")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


async def _upload(
    db: AsyncSession,
    day: datetime.date,
    meal_time: datetime.datetime | None = None,
) -> Photo:
    upload = UploadFile(filename="test.png", file=io.BytesIO(_png_bytes()))
    service = PhotoService(db, FoodAnalysisOrchestrator())
    return await service.upload(
        entry_date=day,
        file=upload,
        label=None,
        meal_time=meal_time,
        background_tasks=BackgroundTasks(),
    )


# ---------------------------------------------------------------------------
# meal_time on Photo upload
# ---------------------------------------------------------------------------


async def test_upload_without_meal_time_defaults_to_now(
    async_db: AsyncSession, isolated_storage: None
) -> None:
    day = datetime.date(2026, 5, 15)
    await _make_entry(async_db, day)
    before = datetime.datetime.utcnow()

    photo = await _upload(async_db, day)

    after = datetime.datetime.utcnow()
    assert photo.meal_time is not None
    # Allow a 5-second window around test execution time
    assert (
        before - datetime.timedelta(seconds=5)
        <= photo.meal_time
        <= after + datetime.timedelta(seconds=5)
    )


async def test_upload_with_explicit_meal_time_persists_it(
    async_db: AsyncSession, isolated_storage: None
) -> None:
    day = datetime.date(2026, 5, 15)
    await _make_entry(async_db, day)
    explicit_time = datetime.datetime(2026, 5, 15, 8, 30, 0)

    photo = await _upload(async_db, day, meal_time=explicit_time)

    assert photo.meal_time == explicit_time


# ---------------------------------------------------------------------------
# PATCH /photos/{photo_id}
# ---------------------------------------------------------------------------


async def test_patch_updates_meal_time(async_db: AsyncSession, isolated_storage: None) -> None:
    day = datetime.date(2026, 5, 15)
    await _make_entry(async_db, day)
    photo = await _upload(async_db, day)

    new_time = datetime.datetime(2026, 5, 15, 12, 0, 0)
    service = PhotoService(async_db, FoodAnalysisOrchestrator())
    updated = await service.update_photo(photo.id, PhotoUpdate(meal_time=new_time))

    assert updated.id == photo.id
    assert updated.meal_time == new_time


async def test_patch_missing_photo_raises_not_found(
    async_db: AsyncSession,
) -> None:
    service = PhotoService(async_db, FoodAnalysisOrchestrator())
    with pytest.raises(NotFoundError):
        await service.update_photo(99999, PhotoUpdate(meal_time=datetime.datetime.utcnow()))


# ---------------------------------------------------------------------------
# alcohol_units / caffeine_servings on Entry (round-trip via ORM)
# ---------------------------------------------------------------------------


async def test_entry_alcohol_caffeine_persist(async_db: AsyncSession) -> None:
    entry = Entry(
        date=datetime.date(2026, 5, 20),
        overall=3,
        bloating=1,
        stool_normal=False,
        joint_pain=0,
        neuro=0,
        sleep_quality=3,
        stress=2,
        diet_risk="low",
        supplements="",
        sick=False,
        hot_shower=False,
        alcohol_units=2,
        caffeine_servings=3,
    )
    async_db.add(entry)
    await async_db.commit()
    await async_db.refresh(entry)

    assert entry.alcohol_units == 2
    assert entry.caffeine_servings == 3


async def test_entry_alcohol_caffeine_default_null(async_db: AsyncSession) -> None:
    entry = Entry(
        date=datetime.date(2026, 5, 21),
        overall=3,
        bloating=1,
        stool_normal=False,
        joint_pain=0,
        neuro=0,
        sleep_quality=3,
        stress=2,
        diet_risk="low",
        supplements="",
        sick=False,
        hot_shower=False,
    )
    async_db.add(entry)
    await async_db.commit()
    await async_db.refresh(entry)

    assert entry.alcohol_units is None
    assert entry.caffeine_servings is None


async def test_entry_update_alcohol_caffeine(async_db: AsyncSession) -> None:
    entry = await _make_entry(async_db, datetime.date(2026, 5, 22))
    entry.alcohol_units = 1
    entry.caffeine_servings = 4
    await async_db.commit()
    await async_db.refresh(entry)

    assert entry.alcohol_units == 1
    assert entry.caffeine_servings == 4


# ---------------------------------------------------------------------------
# Schema validation for alcohol_units / caffeine_servings bounds
# ---------------------------------------------------------------------------


def test_entry_schema_validation_bounds() -> None:
    from app.schemas.entry import EntryCreate
    import pydantic

    # ge=0 lower bound
    with pytest.raises(pydantic.ValidationError):
        EntryCreate(
            date=datetime.date(2026, 5, 15),
            overall=3,
            bloating=1,
            joint_pain=0,
            neuro=0,
            sleep_quality=3,
            stress=2,
            diet_risk="low",
            supplements="",
            sick=False,
            alcohol_units=-1,
        )

    # le=10 upper bound
    with pytest.raises(pydantic.ValidationError):
        EntryCreate(
            date=datetime.date(2026, 5, 15),
            overall=3,
            bloating=1,
            joint_pain=0,
            neuro=0,
            sleep_quality=3,
            stress=2,
            diet_risk="low",
            supplements="",
            sick=False,
            caffeine_servings=11,
        )
