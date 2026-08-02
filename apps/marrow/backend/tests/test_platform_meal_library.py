"""Tests for the platform meal library (mockup A)."""

from __future__ import annotations

import datetime
import json
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.dietary_ingredient import DietaryIngredient
from app.models.photo_analysis import PhotoAnalysis
from app.models.platform_meal import PlatformMeal, PlatformMealIngredient
from app.services.meals import MealService

_DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "platform_meals.json"
TARGET_DAY = datetime.date(2026, 8, 2)


@pytest_asyncio.fixture
async def platform_library(async_db: AsyncSession) -> None:
    """Seed platform meals from the same JSON the migration uses."""
    meals = json.loads(_DATA_PATH.read_text(encoding="utf-8"))
    for meal_data in meals:
        meal = PlatformMeal(
            slug=meal_data["slug"],
            name=meal_data["name"],
            cuisine=meal_data["cuisine"],
            icon_key=meal_data["icon_key"],
            sort_order=meal_data["sort_order"],
            is_active=True,
        )
        async_db.add(meal)
        await async_db.flush()
        for index, canonical_name in enumerate(meal_data["ingredients"]):
            async_db.add(
                PlatformMealIngredient(
                    platform_meal_id=meal.id,
                    canonical_name=canonical_name,
                    sort_order=(index + 1) * 10,
                )
            )
    await async_db.commit()


@pytest_asyncio.fixture
async def dietary_chorizo(async_db: AsyncSession) -> None:
    async_db.add(
        DietaryIngredient(
            canonical_name="chorizo",
            category="meat",
            histamine_score=3,
            contains_gluten=False,
            contains_dairy=False,
        )
    )
    await async_db.commit()


async def _platform_meal_id(async_db: AsyncSession, slug: str) -> int:
    meal = (
        await async_db.execute(select(PlatformMeal).where(PlatformMeal.slug == slug))
    ).scalar_one()
    return meal.id


async def test_library_lists_arroz_de_pato(async_db: AsyncSession, platform_library: None) -> None:
    meals = await MealService(async_db).list_library()
    slugs = {meal.slug for meal in meals}
    assert "arroz-de-pato" in slugs


async def test_library_cuisine_filter_portuguese(
    async_db: AsyncSession, platform_library: None
) -> None:
    meals = await MealService(async_db).list_library(cuisine="Portuguese")
    assert meals
    assert all(meal.cuisine == "Portuguese" for meal in meals)
    assert {meal.slug for meal in meals} >= {
        "arroz-de-pato",
        "bifana",
        "francesinha",
        "pastel-de-nata",
    }


async def test_library_search_arroz(async_db: AsyncSession, platform_library: None) -> None:
    meals = await MealService(async_db).list_library(q="arroz")
    slugs = {meal.slug for meal in meals}
    assert "arroz-de-pato" in slugs
    assert "arroz-con-pollo" in slugs


async def test_log_from_library_creates_confirmed_icon_only_meal(
    async_db: AsyncSession,
    platform_library: None,
    dietary_chorizo: None,
) -> None:
    platform_id = await _platform_meal_id(async_db, "arroz-de-pato")
    photo = await MealService(async_db).log_from_library(TARGET_DAY, platform_id)

    assert photo.filename is None
    assert photo.has_image is False
    assert photo.icon_key == "duck"

    analysis = (
        await async_db.execute(select(PhotoAnalysis).where(PhotoAnalysis.photo_id == photo.id))
    ).scalar_one()
    assert analysis.status == "confirmed"
    assert analysis.dish_name == "Arroz de pato"
    assert analysis.cuisine == "Portuguese"


async def test_log_from_library_arroz_flags_high_histamine(
    async_db: AsyncSession,
    platform_library: None,
    dietary_chorizo: None,
) -> None:
    meals = await MealService(async_db).list_library()
    arroz = next(meal for meal in meals if meal.slug == "arroz-de-pato")
    assert "high-histamine" in arroz.diet_flags


async def test_clone_library_meal_without_bytes(
    async_db: AsyncSession,
    platform_library: None,
    dietary_chorizo: None,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    photo_dir = tmp_path / "photos"
    photo_dir.mkdir()
    monkeypatch.setattr(settings, "photo_dir", str(photo_dir))

    platform_id = await _platform_meal_id(async_db, "arroz-de-pato")
    source = await MealService(async_db).log_from_library(TARGET_DAY, platform_id)
    clone_day = datetime.date(2026, 8, 3)

    cloned = await MealService(async_db).clone(clone_day, source.id)

    assert cloned.filename is None
    assert cloned.has_image is False
    assert cloned.icon_key == "duck"
    assert cloned.id != source.id
    assert list(photo_dir.iterdir()) == []


async def test_photo_file_for_library_meal_returns_404(
    async_db: AsyncSession,
    platform_library: None,
    authed_client: AsyncClient,
) -> None:
    platform_id = await _platform_meal_id(async_db, "arroz-de-pato")
    photo = await MealService(async_db).log_from_library(TARGET_DAY, platform_id)

    resp = await authed_client.get(f"/api/v1/photos/{photo.id}/file")
    assert resp.status_code == 404


async def test_delete_entry_with_library_meal_skips_storage(
    async_db: AsyncSession,
    platform_library: None,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Nullable filename must not be passed to delete_photo (class-of-bug audit)."""
    photo_dir = tmp_path / "photos"
    photo_dir.mkdir()
    monkeypatch.setattr(settings, "photo_dir", str(photo_dir))

    platform_id = await _platform_meal_id(async_db, "arroz-de-pato")
    await MealService(async_db).log_from_library(TARGET_DAY, platform_id)

    from app.services.entries import EntryService

    await EntryService(async_db).delete_entry(TARGET_DAY)

    assert list(photo_dir.iterdir()) == []
    assert (
        await async_db.execute(
            select(PhotoAnalysis).where(PhotoAnalysis.dish_name == "Arroz de pato")
        )
    ).scalar_one_or_none() is None


async def test_delete_library_photo_skips_storage(
    async_db: AsyncSession,
    platform_library: None,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    photo_dir = tmp_path / "photos"
    photo_dir.mkdir()
    monkeypatch.setattr(settings, "photo_dir", str(photo_dir))

    platform_id = await _platform_meal_id(async_db, "arroz-de-pato")
    photo = await MealService(async_db).log_from_library(TARGET_DAY, platform_id)

    from app.services.food_analysis_orchestrator import FoodAnalysisOrchestrator
    from app.services.meal_tags import MealTagService
    from app.services.photos import PhotoService

    await PhotoService(async_db, FoodAnalysisOrchestrator(), MealTagService(async_db)).delete(
        photo.id
    )

    assert list(photo_dir.iterdir()) == []


async def test_next_filename_ignores_null_library_rows(
    async_db: AsyncSession,
    platform_library: None,
) -> None:
    platform_id = await _platform_meal_id(async_db, "arroz-de-pato")
    await MealService(async_db).log_from_library(TARGET_DAY, platform_id)

    from app.services.entries import get_or_create_entry
    from app.services.photos import next_photo_filename

    entry = await get_or_create_entry(async_db, TARGET_DAY)
    name = await next_photo_filename(async_db, entry)
    assert name == f"{TARGET_DAY.isoformat()}_photo-1.jpg"
