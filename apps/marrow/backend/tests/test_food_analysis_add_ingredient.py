"""HTTP-level tests for POST /photos/{id}/analysis/ingredients."""

from __future__ import annotations

import datetime
import uuid

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth_context import user_id_ctx
from app.models.entry import Entry
from app.models.photo import Photo
from app.models.photo_analysis import PhotoAnalysis
from app.models.photo_ingredient import PhotoIngredient
from app.tenant import apply_session_user_id, owned_by_user
from tests.conftest import authed_user_id

_DATE = datetime.date(2026, 4, 1)


async def _make_photo_with_analysis(db: AsyncSession, user_id: uuid.UUID) -> int:
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
    analysis = PhotoAnalysis(user_id=user_id, photo_id=photo.id, status="confirmed")
    db.add(analysis)
    await db.flush()
    await db.commit()
    return photo.id


async def test_add_ingredient_unauthenticated_401(async_client: AsyncClient) -> None:
    resp = await async_client.post(
        "/api/v1/photos/1/analysis/ingredients",
        json={"name": "Tomato"},
    )
    assert resp.status_code == 401


async def test_add_ingredient_missing_analysis_404(authed_client: AsyncClient) -> None:
    resp = await authed_client.post(
        "/api/v1/photos/999999/analysis/ingredients",
        json={"name": "Tomato"},
    )
    assert resp.status_code == 404


async def test_add_ingredient_sets_authenticated_user_id(
    authed_client: AsyncClient, async_db: AsyncSession
) -> None:
    user_id = await authed_user_id(authed_client)
    photo_id = await _make_photo_with_analysis(async_db, user_id)

    resp = await authed_client.post(
        f"/api/v1/photos/{photo_id}/analysis/ingredients",
        json={"name": "Toma"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Toma"
    assert body["user_edited"] is True

    token = user_id_ctx.set(user_id)
    try:
        await apply_session_user_id(async_db, user_id)
        row = (
            await async_db.execute(
                select(PhotoIngredient).where(
                    owned_by_user(PhotoIngredient.user_id),
                    PhotoIngredient.id == body["id"],
                )
            )
        ).scalar_one()
    finally:
        user_id_ctx.reset(token)

    assert row.user_id == user_id
    assert row.name == "Toma"
