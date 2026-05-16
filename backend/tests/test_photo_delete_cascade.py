"""Regression test for the production bug where deleting a Photo failed with:
    sqlite3.IntegrityError: NOT NULL constraint failed: photo_analyses.photo_id

Caused by missing cascade on Photo.analysis — SQLAlchemy tried to NULL the
FK on photo delete instead of deleting the orphaned analysis row.
"""

from __future__ import annotations

import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entry import Entry
from app.models.photo import Photo
from app.models.photo_analysis import PhotoAnalysis
from app.models.photo_ingredient import PhotoIngredient


async def _make_entry_with_analyzed_photo(
    db: AsyncSession,
) -> tuple[Entry, Photo]:
    """Build a realistic graph: entry -> photo -> analysis -> ingredients."""
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
    """The exact production failure: deleting a Photo that has a
    PhotoAnalysis must NOT raise IntegrityError. The analysis row should
    be deleted along with the photo."""
    _, photo = await _make_entry_with_analyzed_photo(async_db)
    photo_id = photo.id
    # Expire then re-fetch the photo so the ORM hydrates `analysis` and
    # knows to issue the dependent DELETE before the FK check fires.
    async_db.expire_all()
    photo = (
        await async_db.execute(select(Photo).where(Photo.id == photo_id))
    ).scalar_one()
    _ = photo.analysis  # ensure the relationship is materialised

    # Sanity: analysis + ingredients exist before delete
    assert (
        await async_db.execute(
            select(func.count())
            .select_from(PhotoAnalysis)
            .where(PhotoAnalysis.photo_id == photo_id)
        )
    ).scalar_one() == 1
    assert (
        await async_db.execute(
            select(func.count())
            .select_from(PhotoIngredient)
            .join(PhotoAnalysis)
            .where(PhotoAnalysis.photo_id == photo_id)
        )
    ).scalar_one() == 2

    await async_db.delete(photo)
    await async_db.commit()  # would raise IntegrityError without the cascade

    # Photo gone
    assert (
        await async_db.execute(select(Photo).where(Photo.id == photo_id))
    ).scalar_one_or_none() is None
    # Analysis cascaded
    assert (
        await async_db.execute(
            select(func.count())
            .select_from(PhotoAnalysis)
            .where(PhotoAnalysis.photo_id == photo_id)
        )
    ).scalar_one() == 0
    # Ingredients cascaded through the analysis
    assert (
        await async_db.execute(select(func.count()).select_from(PhotoIngredient))
    ).scalar_one() == 0


async def test_delete_photo_without_analysis_still_works(
    async_db: AsyncSession,
) -> None:
    """Photos that were never analyzed should also delete cleanly."""
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


async def test_delete_entry_cascades_to_photo_and_analysis(
    async_db: AsyncSession,
) -> None:
    """Deleting an Entry should also wipe its photos and their analyses
    (Entry.photos already has cascade='all, delete-orphan')."""
    entry, _ = await _make_entry_with_analyzed_photo(async_db)
    entry_id = entry.id

    # Expire then re-fetch so the cascade traversal sees photos + their
    # analysis rows (the SQLite tests passed because SQLite didn't enforce
    # FK constraints; Postgres does).
    async_db.expire_all()
    entry = (
        await async_db.execute(select(Entry).where(Entry.id == entry_id))
    ).scalar_one()
    for photo in entry.photos:
        _ = photo.analysis

    await async_db.delete(entry)
    await async_db.commit()

    assert (
        await async_db.execute(select(Entry).where(Entry.id == entry_id))
    ).scalar_one_or_none() is None
    assert (
        await async_db.execute(select(func.count()).select_from(Photo))
    ).scalar_one() == 0
    assert (
        await async_db.execute(select(func.count()).select_from(PhotoAnalysis))
    ).scalar_one() == 0
    assert (
        await async_db.execute(select(func.count()).select_from(PhotoIngredient))
    ).scalar_one() == 0
