"""Tests for vision catalog context wiring (#vision-catalog-context)."""

from __future__ import annotations

import datetime
import os
import uuid
from typing import Optional
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.models.dietary_ingredient import DietaryIngredient
from app.models.entry import Entry
from app.models.ingredient_alias import IngredientAlias
from app.models.photo import Photo
from app.models.photo_analysis import PhotoAnalysis
from app.models.photo_ingredient import PhotoIngredient
from app.services.catalog_context import (
    CATALOG_CONTEXT_MAX_ENTRIES,
    _TRUNCATION_NOTE,
    build_catalog_context,
    format_catalog_context,
)
from app.services.vision_prompt import CATALOG_PROMPT_ADDENDUM, build_messages


# ---------------------------------------------------------------------------
# format_catalog_context / build_catalog_context
# ---------------------------------------------------------------------------


def test_format_catalog_context_empty() -> None:
    assert format_catalog_context([]) == ""


async def test_build_catalog_context_empty(
    async_db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _empty_items(self, *args, **kwargs) -> list[DietaryIngredient]:
        return []

    monkeypatch.setattr(
        "app.services.catalog_context.DietaryIngredientCatalogService.list_items",
        _empty_items,
    )
    assert await build_catalog_context(async_db) == ""


def test_format_catalog_context_cilantro_with_alias() -> None:
    cilantro = DietaryIngredient(canonical_name="cilantro")
    cilantro.aliases = [
        IngredientAlias(alias="coriander", canonical_name="cilantro"),
    ]
    result = format_catalog_context([cilantro])
    assert result == "cilantro [aliases: coriander]"


async def test_build_catalog_context_cilantro_with_alias(async_db: AsyncSession) -> None:
    user_id = uuid.UUID(settings.default_storage_user_id)
    item = DietaryIngredient(user_id=user_id, canonical_name="cilantro", histamine_score=0)
    async_db.add(item)
    await async_db.flush()
    async_db.add(IngredientAlias(user_id=user_id, alias="coriander", canonical_name="cilantro"))
    await async_db.commit()

    result = await build_catalog_context(async_db)
    assert "cilantro [aliases: coriander]" in result


def test_format_catalog_context_soft_truncates_at_500() -> None:
    items = [DietaryIngredient(canonical_name=f"ingredient-{i:04d}") for i in range(501)]
    result = format_catalog_context(items)
    assert result.startswith(_TRUNCATION_NOTE)
    lines = result.split("\n")
    assert lines[0] == _TRUNCATION_NOTE
    assert len(lines) == CATALOG_CONTEXT_MAX_ENTRIES + 1
    assert all(line.startswith("ingredient-") for line in lines[1:])


async def test_build_catalog_context_excludes_archived(async_db: AsyncSession) -> None:
    user_id = uuid.UUID(settings.default_storage_user_id)
    async_db.add(
        DietaryIngredient(user_id=user_id, canonical_name="vision-catalog-active-ingredient")
    )
    async_db.add(
        DietaryIngredient(
            user_id=user_id,
            canonical_name="vision-catalog-archived-ingredient",
            archived=True,
        )
    )
    await async_db.commit()

    result = await build_catalog_context(async_db)
    assert "vision-catalog-active-ingredient" in result
    assert "vision-catalog-archived-ingredient" not in result


# ---------------------------------------------------------------------------
# build_messages
# ---------------------------------------------------------------------------


def test_build_messages_includes_catalog_addendum() -> None:
    catalog = "cilantro [aliases: coriander]"
    messages = build_messages(b"\xff\xd8\xff", catalog_context=catalog)
    system = messages[0]["content"]
    assert "User ingredient catalog" in system
    assert CATALOG_PROMPT_ADDENDUM.strip() in system
    assert catalog in system


@pytest.mark.parametrize("catalog_context", [None, ""])
def test_build_messages_omits_catalog_addendum_when_empty(
    catalog_context: Optional[str],
) -> None:
    messages = build_messages(b"\xff\xd8\xff", catalog_context=catalog_context)
    system = messages[0]["content"]
    assert "User ingredient catalog" not in system
    assert CATALOG_PROMPT_ADDENDUM.strip() not in system


# ---------------------------------------------------------------------------
# Orchestrator integration
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def db_with_photo_and_cilantro(
    async_db: AsyncSession, async_engine, monkeypatch: pytest.MonkeyPatch
) -> tuple[AsyncSession, int]:
    real_maker = async_sessionmaker(async_engine, expire_on_commit=False, class_=AsyncSession)
    user_id = uuid.UUID(settings.default_storage_user_id)

    async with real_maker() as setup_session:
        cilantro = DietaryIngredient(user_id=user_id, canonical_name="cilantro", histamine_score=0)
        setup_session.add(cilantro)
        await setup_session.flush()
        setup_session.add(
            IngredientAlias(user_id=user_id, alias="coriander", canonical_name="cilantro")
        )

        entry = Entry(
            user_id=user_id,
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
            user_id=user_id,
            entry_id=entry.id,
            filename="vision-catalog-test.jpg",
            original_filename="vision-catalog-test.jpg",
            created_at=datetime.datetime.utcnow(),
        )
        setup_session.add(photo)
        await setup_session.commit()
        await setup_session.refresh(photo)
        photo_id = photo.id
        entry_id = entry.id

    monkeypatch.setattr("app.services.food_analysis_orchestrator.async_session_maker", real_maker)

    try:
        yield async_db, photo_id
    finally:
        async with real_maker() as cleanup:
            await cleanup.execute(
                PhotoIngredient.__table__.delete().where(
                    PhotoIngredient.analysis_id.in_(
                        select(PhotoAnalysis.id).where(PhotoAnalysis.photo_id == photo_id)
                    )
                )
            )
            await cleanup.execute(
                PhotoAnalysis.__table__.delete().where(PhotoAnalysis.photo_id == photo_id)
            )
            await cleanup.execute(Photo.__table__.delete().where(Photo.id == photo_id))
            await cleanup.execute(Entry.__table__.delete().where(Entry.id == entry_id))
            await cleanup.execute(
                IngredientAlias.__table__.delete().where(
                    IngredientAlias.canonical_name == "cilantro"
                )
            )
            await cleanup.execute(
                DietaryIngredient.__table__.delete().where(
                    DietaryIngredient.canonical_name == "cilantro"
                )
            )
            await cleanup.commit()


async def _run_trigger_with_captured_messages(
    db_with_photo_and_cilantro: tuple[AsyncSession, int],
    monkeypatch: pytest.MonkeyPatch,
    vision_json: str,
) -> tuple[PhotoAnalysis, list[dict]]:
    _, photo_id = db_with_photo_and_cilantro
    import app.config as cfg_mod

    monkeypatch.setattr(cfg_mod.settings, "openrouter_api_key", "test-key")
    monkeypatch.setattr(cfg_mod.settings, "food_analysis_enabled", True)
    monkeypatch.setattr(cfg_mod.settings, "photo_dir", "/tmp")

    captured: dict[str, list[dict]] = {}

    class _FakeClient:
        def __init__(self, api_key: str, default_model: str) -> None:
            pass

        async def complete_with_image(self, messages: list[dict], **kwargs) -> str:
            captured["messages"] = messages
            return vision_json

    monkeypatch.setattr("app.services.llm.openrouter.OpenRouterClient", _FakeClient)

    os.makedirs(cfg_mod.settings.photo_dir, exist_ok=True)
    with open(os.path.join(cfg_mod.settings.photo_dir, "vision-catalog-test.jpg"), "wb") as f:
        f.write(b"\xff\xd8\xff\xd9")

    from app.services import food_analysis_orchestrator as fa

    await fa.trigger_analysis_background(photo_id)

    async with fa.async_session_maker() as verify:
        analysis = (
            await verify.execute(select(PhotoAnalysis).where(PhotoAnalysis.photo_id == photo_id))
        ).scalar_one()
    return analysis, captured["messages"]


async def test_orchestrator_passes_catalog_to_build_messages(
    db_with_photo_and_cilantro: tuple[AsyncSession, int],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    analysis, messages = await _run_trigger_with_captured_messages(
        db_with_photo_and_cilantro,
        monkeypatch,
        '{"dish_name":"salsa","confidence":0.9,'
        '"ingredients":[{"name":"cilantro","visible":true,"confidence":0.9}]}',
    )
    system = messages[0]["content"]
    assert analysis.status == "confirmed"
    assert "User ingredient catalog" in system
    assert "cilantro [aliases: coriander]" in system


async def test_orchestrator_persists_canonical_name_from_catalog(
    db_with_photo_and_cilantro: tuple[AsyncSession, int],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    analysis, _ = await _run_trigger_with_captured_messages(
        db_with_photo_and_cilantro,
        monkeypatch,
        '{"dish_name":"salsa","confidence":0.9,'
        '"ingredients":[{"name":"cilantro","visible":true,"confidence":0.9}]}',
    )

    from app.services import food_analysis_orchestrator as fa

    async with fa.async_session_maker() as verify:
        ingredient = (
            await verify.execute(
                select(PhotoIngredient).where(PhotoIngredient.analysis_id == analysis.id)
            )
        ).scalar_one()
    assert ingredient.name == "cilantro"
    assert ingredient.canonical_name == "cilantro"


async def test_orchestrator_continues_when_catalog_load_fails(
    db_with_photo_and_cilantro: tuple[AsyncSession, int],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.food_analysis_orchestrator.build_catalog_context",
        AsyncMock(side_effect=RuntimeError("catalog unavailable")),
    )

    analysis, messages = await _run_trigger_with_captured_messages(
        db_with_photo_and_cilantro,
        monkeypatch,
        '{"dish_name":"rice","confidence":0.9,'
        '"ingredients":[{"name":"rice","visible":true,"confidence":0.9}]}',
    )
    system = messages[0]["content"]
    assert analysis.status == "confirmed"
    assert "User ingredient catalog" not in system
