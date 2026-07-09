"""Regression tests for BYOK credential resolution (#186)."""

from __future__ import annotations

import datetime

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.entry import Entry
from app.models.photo import Photo
from app.models.photo_analysis import PhotoAnalysis
from app.models.user_settings import UserSettings
from app.services.llm.encryption import encrypt


@pytest.fixture
def fernet_key(monkeypatch: pytest.MonkeyPatch) -> str:
    from cryptography.fernet import Fernet

    key = Fernet.generate_key().decode()
    import app.config as cfg_mod

    monkeypatch.setattr(cfg_mod.settings, "settings_encryption_key", key)
    import importlib
    import app.services.llm.encryption as enc_mod

    importlib.reload(enc_mod)
    return key


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
            await cleanup.execute(UserSettings.__table__.delete().where(UserSettings.id == 1))
            await cleanup.commit()


async def test_lab_extraction_uses_resolve_path(
    async_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.schemas.lab_marker import CatalogHint
    from app.services import lab_extraction as extraction_module
    from app.services.lab_extraction import LabExtractionService

    resolved: list[str] = []

    async def fake_resolve(db: AsyncSession) -> tuple[str, str]:
        resolved.append("called")
        return ("resolved-key", "test/model")

    monkeypatch.setattr(
        "app.services.llm.factory.resolve_llm_credentials",
        fake_resolve,
    )

    async def fake_call(messages, model, api_key):
        assert api_key == "resolved-key"
        return '{"lab":{"lab_date":"2026-05-01","name":"T","type":"blood","lab_location":null,"notes":null},"markers":[],"confidence":0.9}'

    monkeypatch.setattr(extraction_module, "_call_openrouter", fake_call)

    hints = [
        CatalogHint(
            canonical="hemoglobin",
            display="Hemoglobin",
            aliases=[],
            common_units=["g/dL"],
        )
    ]
    await LabExtractionService(async_db).extract_text("doc", hints)
    assert resolved == ["called"]


async def test_trigger_with_byok_only_calls_openrouter(
    db_with_photo: tuple[AsyncSession, int],
    monkeypatch: pytest.MonkeyPatch,
    fernet_key: str,
) -> None:
    session, photo_id = db_with_photo
    import app.config as cfg_mod

    monkeypatch.setattr(cfg_mod.settings, "openrouter_api_key", "")
    monkeypatch.setattr(cfg_mod.settings, "food_analysis_enabled", True)
    monkeypatch.setattr(cfg_mod.settings, "photo_dir", "/tmp")

    from app.services import food_analysis as fa

    async with fa.async_session_maker() as setup:
        setup.add(
            UserSettings(
                id=1,
                llm_api_key_encrypted=encrypt("byok-test-key"),
            )
        )
        await setup.commit()

    called: list[str] = []

    class _FakeClient:
        def __init__(self, api_key: str, default_model: str) -> None:
            called.append(api_key)

        async def complete_with_image(self, *args, **kwargs) -> str:
            return (
                '{"dish_name":"Test Dish","cuisine":"test","confidence":0.9,'
                '"ingredients":[{"name":"rice","visible":true,"confidence":0.9}]}'
            )

    monkeypatch.setattr("app.services.llm.openrouter.OpenRouterClient", _FakeClient)

    # Photo file is read from disk — create a minimal file for the trigger.
    import os

    os.makedirs(cfg_mod.settings.photo_dir, exist_ok=True)
    with open(os.path.join(cfg_mod.settings.photo_dir, "test.jpg"), "wb") as f:
        f.write(b"\xff\xd8\xff\xd9")

    await fa.trigger_analysis_background(photo_id)

    assert called == ["byok-test-key"]
    async with fa.async_session_maker() as verify:
        analysis = (
            await verify.execute(select(PhotoAnalysis).where(PhotoAnalysis.photo_id == photo_id))
        ).scalar_one_or_none()
    assert analysis is not None
    assert analysis.status == "complete"
    assert analysis.dish_name == "Test Dish"
