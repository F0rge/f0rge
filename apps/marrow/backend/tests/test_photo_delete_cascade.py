"""Regression test for photo delete with meal-scoped analysis."""

from __future__ import annotations

import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.meals import MealCRUD
from app.models.entry import Entry
from app.models.photo import Photo
from app.models.photo_analysis import PhotoAnalysis
from app.models.photo_ingredient import PhotoIngredient


async def _make_entry_with_analyzed_photo(
    db: AsyncSession,
) -> tuple[Entry, Photo]:
    """Build a realistic graph: entry -> photo -> meal analysis -> ingredients."""
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
    db.add(entry)
    await db.commit()
    await db.refresh(entry)

    photo = Photo(
        entry_id=entry.id,
        filename="2026-05-15_photo-1.jpg",
        original_filename="lunch.jpg",
        created_at=datetime.datetime.utcnow(),
    )
    db.add(photo)
    await db.commit()
    await db.refresh(photo)

    analysis = PhotoAnalysis(
        photo_id=photo.id,
        status="confirmed",
        dish_name="pasta carbonara",
        dish_confidence=0.92,
        model_id="google/gemini-3-flash-preview",
    )
    db.add(analysis)
    await db.commit()
    await db.refresh(analysis)

    db.add_all(
        [
            PhotoIngredient(
                analysis_id=analysis.id,
                name="spaghetti",
                visible=True,
                confidence=0.95,
                user_edited=False,
            ),
            PhotoIngredient(
                analysis_id=analysis.id,
                name="egg",
                visible=True,
                confidence=0.9,
                user_edited=False,
            ),
        ]
    )
    await db.commit()
    return entry, photo


async def test_delete_photo_with_analysis_cascades(async_db: AsyncSession) -> None:
    """Deleting the sole placement removes the orphaned meal and its analysis."""
    _, photo = await _make_entry_with_analyzed_photo(async_db)
    photo_id = photo.id
    meal_id = photo.meal_id
    async_db.expire_all()
    photo = (await async_db.execute(select(Photo).where(Photo.id == photo_id))).scalar_one()

    assert (
        await async_db.execute(
            select(func.count())
            .select_from(PhotoAnalysis)
            .where(PhotoAnalysis.meal_id == meal_id)
        )
    ).scalar_one() == 1

    await async_db.delete(photo)
    await async_db.commit()

    assert (
        await async_db.execute(select(Photo).where(Photo.id == photo_id))
    ).scalar_one_or_none() is None
    assert (
        await async_db.execute(
            select(func.count()).select_from(PhotoAnalysis).where(PhotoAnalysis.meal_id == meal_id)
        )
    ).scalar_one() == 0
    assert (
        await async_db.execute(select(func.count()).select_from(PhotoIngredient))
    ).scalar_one() == 0


async def test_delete_photo_without_analysis_still_works(async_db: AsyncSession) -> None:
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
    async_db.add(entry)
    await async_db.commit()
    await async_db.refresh(entry)
    photo = Photo(
        entry_id=entry.id,
        filename="x.jpg",
        created_at=datetime.datetime.utcnow(),
    )
    async_db.add(photo)
    await async_db.commit()
    await async_db.refresh(photo)
    photo_id = photo.id

    await async_db.delete(photo)
    await async_db.commit()

    assert (
        await async_db.execute(select(Photo).where(Photo.id == photo_id))
    ).scalar_one_or_none() is None


async def test_delete_entry_cascades_to_photo_and_analysis(async_db: AsyncSession) -> None:
    entry, _ = await _make_entry_with_analyzed_photo(async_db)
    entry_id = entry.id

    async_db.expire_all()
    entry = (await async_db.execute(select(Entry).where(Entry.id == entry_id))).scalar_one()

    await async_db.delete(entry)
    await async_db.commit()

    assert (
        await async_db.execute(select(Entry).where(Entry.id == entry_id))
    ).scalar_one_or_none() is None
    assert (await async_db.execute(select(func.count()).select_from(Photo))).scalar_one() == 0
    assert (
        await async_db.execute(select(func.count()).select_from(PhotoAnalysis))
    ).scalar_one() == 0
    assert (
        await async_db.execute(select(func.count()).select_from(PhotoIngredient))
    ).scalar_one() == 0


async def test_delete_photo_leaves_shared_meal_analysis(async_db: AsyncSession) -> None:
    """Deleting one placement must not remove analysis while another placement exists."""
    _, source = await _make_entry_with_analyzed_photo(async_db)
    meal_id = source.meal_id
    copy = Photo(
        entry_id=source.entry_id,
        meal_id=meal_id,
        filename="2026-05-15_photo-2.jpg",
        source_photo_id=source.id,
        created_at=datetime.datetime.utcnow(),
    )
    async_db.add(copy)
    await async_db.commit()
    await async_db.refresh(copy)

    await async_db.delete(copy)
    await MealCRUD(async_db).delete_if_orphaned(meal_id)
    await async_db.commit()

    assert (
        await async_db.execute(
            select(func.count()).select_from(PhotoAnalysis).where(PhotoAnalysis.meal_id == meal_id)
        )
    ).scalar_one() == 1
