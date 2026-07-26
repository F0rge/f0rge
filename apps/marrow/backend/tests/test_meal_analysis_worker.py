"""Tests for meal_analysis_queue claim / enqueue / upload seam."""

from __future__ import annotations

import datetime
import io
import uuid
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import BackgroundTasks, UploadFile
from PIL import Image
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.models.entry import Entry
from app.models.meal_analysis_queue import MealAnalysisQueue
from app.models.photo import Photo
from app.models.photo_analysis import PhotoAnalysis
from f0rge_db.tenant import apply_service_role, apply_session_user_id


async def _seed_photo(db: AsyncSession) -> Photo:
    entry = Entry(
        date=datetime.date.today(),
        overall=2,
        bloating=0,
        joint_pain=0,
        neuro=0,
        sleep_quality=2,
        stress=1,
        diet_risk="normal",
        supplements="",
        sick=False,
        hot_shower=False,
        symptoms_json={},
    )
    db.add(entry)
    await db.flush()
    photo = Photo(
        entry_id=entry.id,
        filename="meal-queue.jpg",
        original_filename="meal-queue.jpg",
        created_at=datetime.datetime.utcnow(),
    )
    db.add(photo)
    await db.flush()
    await db.refresh(photo)
    return photo


async def test_claim_batch_returns_pending_rows(async_db: AsyncSession) -> None:
    photo = await _seed_photo(async_db)
    async_db.add(
        MealAnalysisQueue(
            user_id=photo.user_id,
            meal_id=photo.meal_id,
            photo_id=photo.id,
        )
    )
    await async_db.flush()

    from app.meal_analysis_pipeline.worker import _claim_batch

    rows = await _claim_batch(async_db)
    assert len(rows) >= 1
    assert any(r.photo_id == photo.id and r.meal_id == photo.meal_id for r in rows)


async def test_process_pending_once_runs_pipeline_and_deletes(
    async_engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Worker tick against a committed queue row (separate connections)."""
    from app.meal_analysis_pipeline.worker import process_pending_once

    real_maker = async_sessionmaker(async_engine, expire_on_commit=False, class_=AsyncSession)
    monkeypatch.setattr("app.meal_analysis_pipeline.worker.async_session_maker", real_maker)

    run_pipeline = AsyncMock(return_value="confirmed")
    monkeypatch.setattr(
        "app.meal_analysis_pipeline.worker.run_staged_pipeline",
        run_pipeline,
    )

    user_id = uuid.UUID(settings.default_storage_user_id)
    async with real_maker() as setup:
        await apply_session_user_id(setup, user_id)
        photo = await _seed_photo(setup)
        setup.add(
            MealAnalysisQueue(
                user_id=photo.user_id,
                meal_id=photo.meal_id,
                photo_id=photo.id,
            )
        )
        await setup.commit()
        photo_id = photo.id
        meal_id = photo.meal_id
        entry_id = photo.entry_id

    try:
        n = await process_pending_once()
        assert n >= 1
        run_pipeline.assert_awaited()
        assert run_pipeline.await_args.args[0] == photo_id

        async with real_maker() as verify:
            await apply_service_role(verify, "worker")
            remaining = (
                await verify.execute(
                    select(func.count())
                    .select_from(MealAnalysisQueue)
                    .where(MealAnalysisQueue.meal_id == meal_id)
                )
            ).scalar_one()
        assert remaining == 0
    finally:
        async with real_maker() as cleanup:
            await apply_service_role(cleanup, "worker")
            await cleanup.execute(
                text("DELETE FROM meal_analysis_queue WHERE meal_id = :mid"),
                {"mid": meal_id},
            )
            await cleanup.commit()
        async with real_maker() as cleanup:
            await apply_session_user_id(cleanup, user_id)
            await cleanup.execute(
                PhotoAnalysis.__table__.delete().where(PhotoAnalysis.meal_id == meal_id)
            )
            await cleanup.execute(Photo.__table__.delete().where(Photo.id == photo_id))
            await cleanup.execute(text("DELETE FROM meals WHERE id = :mid"), {"mid": meal_id})
            await cleanup.execute(Entry.__table__.delete().where(Entry.id == entry_id))
            await cleanup.commit()


async def test_enqueue_upserts_and_resets_attempts(async_db: AsyncSession) -> None:
    from app.services.meal_analysis_enqueue import enqueue_meal_analysis

    photo = await _seed_photo(async_db)
    async_db.add(
        MealAnalysisQueue(
            user_id=photo.user_id,
            meal_id=photo.meal_id,
            photo_id=photo.id,
            attempts=3,
            last_error="boom",
        )
    )
    await async_db.flush()

    await enqueue_meal_analysis(
        async_db,
        user_id=photo.user_id,
        meal_id=photo.meal_id,
        photo_id=photo.id,
    )

    row = (
        await async_db.execute(
            select(MealAnalysisQueue).where(MealAnalysisQueue.meal_id == photo.meal_id)
        )
    ).scalar_one()
    assert row.attempts == 0
    assert row.last_error is None
    assert row.photo_id == photo.id


async def test_upload_enqueues_pending_analysis(
    async_db: AsyncSession, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services.food_analysis_orchestrator import FoodAnalysisOrchestrator
    from app.services.meal_tags import MealTagService
    from app.services.photos import PhotoService

    photo_dir = tmp_path / "photos"
    photo_dir.mkdir()
    monkeypatch.setattr(settings, "photo_dir", str(photo_dir))
    monkeypatch.setattr(settings, "food_analysis_enabled", True)
    monkeypatch.setattr(settings, "meal_analysis_queue_enabled", True)
    monkeypatch.setattr(settings, "meal_analysis_inline", False)
    monkeypatch.setattr(settings, "openrouter_api_key", "sk-test")

    async def _creds(_db: Any) -> tuple[str, str]:
        return "sk-test", "test-model"

    monkeypatch.setattr("app.services.llm.factory.resolve_llm_credentials", _creds)

    day = datetime.date(2026, 7, 26)
    entry = Entry(
        date=day,
        overall=2,
        bloating=0,
        joint_pain=0,
        neuro=0,
        sleep_quality=2,
        stress=1,
        diet_risk="normal",
        supplements="",
        sick=False,
        hot_shower=False,
        symptoms_json={},
    )
    async_db.add(entry)
    await async_db.commit()
    await async_db.refresh(entry)

    img = Image.new("RGB", (8, 8), color="red")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    service = PhotoService(async_db, FoodAnalysisOrchestrator(), MealTagService(async_db))
    photo = await service.upload(
        entry_date=day,
        file=UploadFile(filename="x.png", file=buf),
        label=None,
        meal_time=None,
        background_tasks=BackgroundTasks(),
    )

    analysis = (
        await async_db.execute(select(PhotoAnalysis).where(PhotoAnalysis.photo_id == photo.id))
    ).scalar_one()
    assert analysis.status == "pending"

    queue_row = (
        await async_db.execute(
            select(MealAnalysisQueue).where(MealAnalysisQueue.photo_id == photo.id)
        )
    ).scalar_one()
    assert queue_row.meal_id == photo.meal_id
    assert queue_row.user_id == uuid.UUID(settings.default_storage_user_id)
