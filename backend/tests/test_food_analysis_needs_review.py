"""Tests for low-confidence photo analysis → needs_review gate (#194)."""

from __future__ import annotations

import datetime

import bcrypt
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.models.entry import Entry
from app.models.photo import Photo
from app.models.photo_analysis import PhotoAnalysis
from app.services.food_analysis import analysis_needs_review
from app.services.vision_prompt import VisionIngredient, VisionResult

TEST_PIN = "1234"
_DATE = datetime.date(2026, 4, 1)


def test_analysis_needs_review_parse_error() -> None:
    result = VisionResult(dish_name="parse_error", confidence=0.0, ingredients=[])
    assert analysis_needs_review(result) is True


def test_analysis_needs_review_low_dish_confidence() -> None:
    result = VisionResult(
        dish_name="Soup",
        confidence=0.69,
        ingredients=[VisionIngredient(name="carrot", confidence=0.9)],
    )
    assert analysis_needs_review(result) is True


def test_analysis_needs_review_low_ingredient_confidence() -> None:
    result = VisionResult(
        dish_name="Salad",
        confidence=0.9,
        ingredients=[VisionIngredient(name="lettuce", confidence=0.49)],
    )
    assert analysis_needs_review(result) is True


def test_analysis_needs_review_high_confidence() -> None:
    result = VisionResult(
        dish_name="Rice bowl",
        confidence=0.9,
        ingredients=[VisionIngredient(name="rice", confidence=0.9)],
    )
    assert analysis_needs_review(result) is False


@pytest_asyncio.fixture
async def db_with_photo(
    async_db: AsyncSession, async_engine, monkeypatch: pytest.MonkeyPatch
) -> tuple[AsyncSession, int]:
    real_maker = async_sessionmaker(async_engine, expire_on_commit=False, class_=AsyncSession)

    async with real_maker() as setup_session:
        entry = Entry(
            date=datetime.date.today(),
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
        setup_session.add(entry)
        await setup_session.commit()
        await setup_session.refresh(entry)

        photo = Photo(
            entry_id=entry.id,
            filename="test.jpg",
            original_filename="test.jpg",
            created_at=datetime.datetime.utcnow(),
        )
        setup_session.add(photo)
        await setup_session.commit()
        await setup_session.refresh(photo)
        photo_id = photo.id
        entry_id = entry.id

    monkeypatch.setattr("app.services.food_analysis.async_session_maker", real_maker)

    try:
        yield async_db, photo_id
    finally:
        async with real_maker() as cleanup:
            await cleanup.execute(
                PhotoAnalysis.__table__.delete().where(PhotoAnalysis.photo_id == photo_id)
            )
            await cleanup.execute(Photo.__table__.delete().where(Photo.id == photo_id))
            await cleanup.execute(Entry.__table__.delete().where(Entry.id == entry_id))
            await cleanup.commit()


async def _run_trigger_with_response(
    db_with_photo: tuple[AsyncSession, int],
    monkeypatch: pytest.MonkeyPatch,
    vision_json: str,
) -> PhotoAnalysis:
    _, photo_id = db_with_photo
    import app.config as cfg_mod

    monkeypatch.setattr(cfg_mod.settings, "openrouter_api_key", "test-key")
    monkeypatch.setattr(cfg_mod.settings, "food_analysis_enabled", True)
    monkeypatch.setattr(cfg_mod.settings, "photo_dir", "/tmp")

    class _FakeClient:
        def __init__(self, api_key: str, default_model: str) -> None:
            pass

        async def complete_with_image(self, *args, **kwargs) -> str:
            return vision_json

    monkeypatch.setattr("app.services.llm.openrouter.OpenRouterClient", _FakeClient)

    import os

    os.makedirs(cfg_mod.settings.photo_dir, exist_ok=True)
    with open(os.path.join(cfg_mod.settings.photo_dir, "test.jpg"), "wb") as f:
        f.write(b"\xff\xd8\xff\xd9")

    from app.services import food_analysis as fa

    await fa.trigger_analysis_background(photo_id)

    async with fa.async_session_maker() as verify:
        analysis = (
            await verify.execute(select(PhotoAnalysis).where(PhotoAnalysis.photo_id == photo_id))
        ).scalar_one()
    return analysis


async def test_trigger_low_dish_confidence_sets_needs_review(
    db_with_photo: tuple[AsyncSession, int],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    analysis = await _run_trigger_with_response(
        db_with_photo,
        monkeypatch,
        '{"dish_name":"Soup","confidence":0.5,'
        '"ingredients":[{"name":"carrot","visible":true,"confidence":0.9}]}',
    )
    assert analysis.status == "needs_review"


async def test_trigger_high_confidence_sets_complete(
    db_with_photo: tuple[AsyncSession, int],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    analysis = await _run_trigger_with_response(
        db_with_photo,
        monkeypatch,
        '{"dish_name":"Rice","confidence":0.9,'
        '"ingredients":[{"name":"rice","visible":true,"confidence":0.9}]}',
    )
    assert analysis.status == "complete"


@pytest.fixture(autouse=True)
def known_pin(monkeypatch: pytest.MonkeyPatch) -> str:
    hashed = bcrypt.hashpw(TEST_PIN.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    monkeypatch.setattr(settings, "pin_hash", hashed)
    return TEST_PIN


@pytest.fixture
async def authed_client(async_client: AsyncClient) -> AsyncClient:
    resp = await async_client.post("/api/v1/auth/login", json={"pin": TEST_PIN})
    assert resp.status_code == 200
    return async_client


async def test_confirm_needs_review_transitions_to_confirmed(
    authed_client: AsyncClient,
    async_db: AsyncSession,
) -> None:
    entry = Entry(
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
    async_db.add(entry)
    await async_db.flush()
    photo = Photo(entry_id=entry.id, filename="meal.jpg")
    async_db.add(photo)
    await async_db.flush()
    async_db.add(
        PhotoAnalysis(
            photo_id=photo.id,
            status="needs_review",
            dish_name="Uncertain dish",
            dish_confidence=0.4,
        )
    )
    await async_db.commit()

    resp = await authed_client.put(f"/api/v1/photos/{photo.id}/analysis/confirm")
    assert resp.status_code == 200
    assert resp.json()["status"] == "confirmed"
