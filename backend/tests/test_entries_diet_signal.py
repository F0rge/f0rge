"""Tests for the compute-on-read diet signal in EntryResponse.

Covers the four scenarios from the Wave 2 brief:
1. User-added flag only (no photos)
2. Photo-derived flags only (no manual)
3. Photo-derived + user-added (combined)
4. Legacy diet_risk with "normal" stripped on parse
"""

from __future__ import annotations

import datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entry import Entry
from app.models.photo import Photo
from app.models.photo_analysis import PhotoAnalysis
from app.models.photo_ingredient import PhotoIngredient
from app.services.entries import get_entry

pytestmark = pytest.mark.asyncio

_BASE_DATE = datetime.date(2026, 1, 10)


async def _make_entry(
    db: AsyncSession,
    *,
    date: datetime.date = _BASE_DATE,
    diet_risk: str = "",
) -> Entry:
    entry = Entry(
        date=date,
        schema_version=3,
        overall=2,
        bloating=0,
        stool_status="normal",
        joint_pain=0,
        neuro=0,
        sleep_quality=2,
        stress=1,
        diet_risk=diet_risk,
        supplements="",
        sick=False,
        hot_shower=False,
        symptoms_json={},
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry


async def _add_confirmed_photo_with_ingredients(
    db: AsyncSession,
    entry: Entry,
    *,
    date: datetime.date = _BASE_DATE,
    ingredients: list[dict],
) -> Photo:
    """Add a confirmed photo with the given ingredient dicts to the entry."""
    photo = Photo(
        entry_id=entry.id,
        filename=f"{date.isoformat()}_photo-1.jpg",
        created_at=datetime.datetime.utcnow(),
    )
    db.add(photo)
    await db.commit()
    await db.refresh(photo)

    analysis = PhotoAnalysis(
        photo_id=photo.id,
        status="confirmed",
        dish_name="test dish",
        dish_confidence=0.9,
        model_id="test-model",
    )
    db.add(analysis)
    await db.commit()
    await db.refresh(analysis)

    for ing_kwargs in ingredients:
        ing = PhotoIngredient(
            analysis_id=analysis.id,
            name=ing_kwargs.get("name", "unknown"),
            visible=ing_kwargs.get("visible", True),
            confidence=ing_kwargs.get("confidence", 0.9),
            user_edited=False,
            histamine_score=ing_kwargs.get("histamine_score", None),
            contains_gluten=ing_kwargs.get("contains_gluten", None),
            contains_dairy=ing_kwargs.get("contains_dairy", None),
            fodmap_oligos=ing_kwargs.get("fodmap_oligos", None),
            fodmap_fructose=ing_kwargs.get("fodmap_fructose", None),
            fodmap_polyols=ing_kwargs.get("fodmap_polyols", None),
            fodmap_lactose=ing_kwargs.get("fodmap_lactose", None),
        )
        db.add(ing)
    await db.commit()
    return photo


# ---------------------------------------------------------------------------
# Scenario 1: user-added flag only, no photos
# ---------------------------------------------------------------------------


async def test_user_added_flag_only_no_photos(async_db: AsyncSession) -> None:
    """Entry with diet_risk=high-fodmap and no photos.

    effective_flags contains only the user-added flag; photo_derived_flags is empty.
    """
    await _make_entry(async_db, diet_risk="high-fodmap")
    response = await get_entry(async_db, _BASE_DATE)

    assert response.effective_flags == ["high-fodmap"]
    assert response.photo_derived_flags == []
    assert response.user_added_flags == ["high-fodmap"]
    assert response.photo_signal is not None
    assert response.photo_signal.scores.histamine_load == 0


# ---------------------------------------------------------------------------
# Scenario 2: photo-derived flags only (high-histamine + dairy), no manual
# ---------------------------------------------------------------------------


async def test_photo_derived_flags_only_no_manual(async_db: AsyncSession) -> None:
    """Entry with confirmed photo ingredients producing high-histamine (load=7) and dairy.

    diet_risk="" → user_added_flags is empty.
    """
    date = datetime.date(2026, 1, 11)
    entry = await _make_entry(async_db, date=date, diet_risk="")
    await _add_confirmed_photo_with_ingredients(
        async_db,
        entry,
        date=date,
        ingredients=[
            # histamine_score=7 → ≥ HISTAMINE_FLAG_THRESHOLD(2) → high-histamine
            {"name": "aged-cheese-1", "histamine_score": 4, "contains_dairy": True},
            {"name": "aged-cheese-2", "histamine_score": 3, "contains_dairy": True},
        ],
    )
    # Expire the cached entry so get_entry re-selects with fresh relationships.
    async_db.expire(entry)

    response = await get_entry(async_db, date)

    assert response.effective_flags == ["dairy", "high-histamine"]
    assert response.photo_derived_flags == ["dairy", "high-histamine"]
    assert response.user_added_flags == []
    assert response.photo_signal is not None
    assert response.photo_signal.scores.histamine_load == 7
    assert response.photo_signal.scores.dairy_count == 2


# ---------------------------------------------------------------------------
# Scenario 3: photo-derived flags + user-added gluten
# ---------------------------------------------------------------------------


async def test_photo_derived_plus_user_added(async_db: AsyncSession) -> None:
    """Photo gives high-histamine+dairy; user added gluten manually.

    effective_flags = union of both; histamine_load unchanged by manual.
    """
    date = datetime.date(2026, 1, 12)
    entry = await _make_entry(async_db, date=date, diet_risk="gluten")
    await _add_confirmed_photo_with_ingredients(
        async_db,
        entry,
        date=date,
        ingredients=[
            {"name": "salami", "histamine_score": 4, "contains_dairy": False},
            {"name": "brie", "histamine_score": 3, "contains_dairy": True},
        ],
    )
    # Expire so get_entry re-fetches with fresh relationships.
    async_db.expire(entry)

    response = await get_entry(async_db, date)

    assert response.effective_flags == ["dairy", "gluten", "high-histamine"]
    assert response.user_added_flags == ["gluten"]
    assert response.photo_signal is not None
    assert response.photo_signal.scores.histamine_load == 7


# ---------------------------------------------------------------------------
# Scenario 4: legacy diet_risk with "normal" stripped
# ---------------------------------------------------------------------------


async def test_legacy_normal_stripped_from_user_added(async_db: AsyncSession) -> None:
    """Legacy diet_risk="normal,high-fodmap" → "normal" is stripped, only "high-fodmap" survives."""
    date = datetime.date(2026, 1, 13)
    await _make_entry(async_db, date=date, diet_risk="normal,high-fodmap")

    response = await get_entry(async_db, date)

    assert "normal" not in response.user_added_flags
    assert response.user_added_flags == ["high-fodmap"]
    assert response.effective_flags == ["high-fodmap"]
