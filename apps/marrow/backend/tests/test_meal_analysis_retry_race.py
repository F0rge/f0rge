"""Retry keeps the analysis id; missing complete/fail callbacks are 410."""

from __future__ import annotations

import datetime
import uuid

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.entry import Entry
from app.models.photo import Photo
from app.models.photo_analysis import PhotoAnalysis
from app.models.photo_ingredient import PhotoIngredient
from tests.conftest import authed_user_id

_DATE = datetime.date(2026, 5, 2)
_PAST = datetime.datetime(2020, 1, 1, 0, 0, 0)


async def _seed_failed_analysis(db: AsyncSession, user_id: uuid.UUID) -> int:
    entry = Entry(
        user_id=user_id,
        date=_DATE,
        schema_version=4,
        overall=2,
        bloating=0,
        stool_status="normal",
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
    photo = Photo(user_id=user_id, entry_id=entry.id, filename="meal.jpg")
    db.add(photo)
    await db.flush()
    analysis = PhotoAnalysis(
        user_id=user_id,
        photo_id=photo.id,
        status="failed",
        dish_name="leftover soup",
        cuisine="unknown",
        dish_confidence=0.4,
        raw_response='{"dish_name":"leftover soup"}',
        error_message="vision timeout",
        created_at=_PAST,
        updated_at=_PAST,
    )
    db.add(analysis)
    await db.flush()
    db.add(
        PhotoIngredient(
            user_id=user_id,
            analysis_id=analysis.id,
            name="onion",
            visible=True,
            confidence=0.6,
        )
    )
    await db.commit()
    return photo.id


async def test_retry_keeps_analysis_id_and_resets_pending(
    authed_client: AsyncClient,
    async_db: AsyncSession,
    monkeypatch,
) -> None:
    enqueued: list[int] = []

    async def _enqueue(photo_id, user_id, background_tasks, *, orchestrator_run) -> None:
        enqueued.append(photo_id)

    monkeypatch.setattr("app.services.food_analysis_enqueue.enqueue_food_analysis", _enqueue)

    user_id = await authed_user_id(authed_client)
    photo_id = await _seed_failed_analysis(async_db, user_id)
    before = await authed_client.get(f"/api/v1/photos/{photo_id}/analysis")
    assert before.status_code == 200
    original_id = before.json()["id"]
    assert before.json()["status"] == "failed"
    assert before.json()["ingredients"]

    resp = await authed_client.put(f"/api/v1/photos/{photo_id}/analysis/retry")
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["id"] == original_id
    assert body["status"] == "pending"
    assert body["error_message"] is None
    assert body["dish_name"] is None
    assert body["cuisine"] is None
    assert body["dish_confidence"] is None
    assert body["ingredients"] == []
    assert body["created_at"].startswith("2020-01-01")
    assert not body["updated_at"].startswith("2020-01-01")
    assert enqueued == [photo_id]

    async_db.expire_all()
    analysis = (
        await async_db.execute(select(PhotoAnalysis).where(PhotoAnalysis.id == original_id))
    ).scalar_one()
    assert analysis.status == "pending"
    assert analysis.error_message is None
    assert analysis.raw_response is None
    ingredients = (
        (
            await async_db.execute(
                select(PhotoIngredient).where(PhotoIngredient.analysis_id == original_id)
            )
        )
        .scalars()
        .all()
    )
    assert ingredients == []


async def test_complete_and_fail_missing_analysis_return_410(
    async_client: AsyncClient, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "airflow_service_token", "svc-token")
    headers = {"Authorization": "Bearer svc-token"}
    user_id = str(uuid.uuid4())
    missing_id = 9_999_999

    complete = await async_client.post(
        f"/api/v1/internal/airflow/meal-analysis/{missing_id}/complete",
        headers=headers,
        json={
            "user_id": user_id,
            "dish_name": "salad",
            "cuisine": None,
            "confidence": 0.5,
            "ingredients": [],
        },
    )
    assert complete.status_code == 410
    assert complete.json() == {"detail": "superseded"}

    fail = await async_client.post(
        f"/api/v1/internal/airflow/meal-analysis/{missing_id}/fail",
        headers=headers,
        json={"user_id": user_id, "error_message": "late failure"},
    )
    assert fail.status_code == 410
    assert fail.json() == {"detail": "superseded"}
