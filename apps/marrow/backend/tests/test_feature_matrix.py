"""Second-engine guard for the per-meal gluten-free / lactose-free scoring gate.

``feature_matrix._compute_dietary_loads`` is a DUPLICATE of the diet_flags
aggregation; a fix in only one engine leaves the other wrong. These tests prove
the override is applied here too, exercising the real ``build_feature_matrix``
(no mocks) so the per-photo loop, selectinload, and dict output are all real.
"""

from __future__ import annotations

import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entry import Entry
from app.models.photo import Photo
from app.models.photo_analysis import PhotoAnalysis
from app.models.photo_ingredient import PhotoIngredient
from app.services.feature_matrix import build_feature_matrix

_DATE = datetime.date(2026, 3, 1)


async def _entry_with_ingredient(
    db: AsyncSession,
    *,
    gluten_free_confirmed: bool = False,
    lactose_free_confirmed: bool = False,
    **ing_kwargs: object,
) -> Entry:
    """One entry -> one confirmed photo/analysis -> one ingredient, committed."""
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
    db.add(entry)
    await db.flush()

    photo = Photo(entry_id=entry.id, filename="meal.jpg")
    db.add(photo)
    await db.flush()

    analysis = PhotoAnalysis(
        photo_id=photo.id,
        status="confirmed",
        gluten_free_confirmed=gluten_free_confirmed,
        lactose_free_confirmed=lactose_free_confirmed,
    )
    db.add(analysis)
    await db.flush()

    ing = PhotoIngredient(analysis_id=analysis.id, name="x", confidence=0.9, **ing_kwargs)
    db.add(ing)
    await db.flush()
    await db.commit()
    return entry


async def _loads(db: AsyncSession) -> dict:
    rows, _ = await build_feature_matrix(db, start_date=_DATE, end_date=_DATE)
    return rows[0]


# ---------------------------------------------------------------------------
# Gluten exposure gate
# ---------------------------------------------------------------------------


async def test_gluten_exposure_off_when_gluten_confirmed(async_db: AsyncSession) -> None:
    await _entry_with_ingredient(
        async_db, gluten_free_confirmed=True, contains_gluten=True, contains_dairy=True
    )
    row = await _loads(async_db)

    assert row["gluten_exposure"] is False
    # Dairy exposure is deliberately unaffected.
    assert row["dairy_exposure"] is True


async def test_gluten_exposure_on_baseline(async_db: AsyncSession) -> None:
    await _entry_with_ingredient(async_db, contains_gluten=True)
    row = await _loads(async_db)

    assert row["gluten_exposure"] is True


# ---------------------------------------------------------------------------
# Lactose sum gate
# ---------------------------------------------------------------------------


async def test_lactose_sum_excludes_lactose_when_confirmed(async_db: AsyncSession) -> None:
    # Lactose high + oligos high; lactose-free set -> lactose sum drops to 0,
    # oligos sum still counts.
    await _entry_with_ingredient(
        async_db,
        lactose_free_confirmed=True,
        fodmap_lactose="high",
        fodmap_oligos="high",
    )
    row = await _loads(async_db)

    assert row["fodmap_lactose_sum"] == 0
    assert row["fodmap_oligos_sum"] == 2


async def test_lactose_sum_baseline(async_db: AsyncSession) -> None:
    await _entry_with_ingredient(async_db, fodmap_lactose="high")
    row = await _loads(async_db)

    assert row["fodmap_lactose_sum"] == 2


async def test_dairy_exposure_unchanged_by_lactose_confirm(async_db: AsyncSession) -> None:
    await _entry_with_ingredient(
        async_db,
        lactose_free_confirmed=True,
        fodmap_lactose="high",
        contains_dairy=True,
    )
    row = await _loads(async_db)

    assert row["dairy_exposure"] is True
    assert row["fodmap_lactose_sum"] == 0
