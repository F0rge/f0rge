"""Regression test for the production bug where deleting a Photo failed with:
    sqlite3.IntegrityError: NOT NULL constraint failed: photo_analyses.photo_id

Caused by missing cascade on Photo.analysis — SQLAlchemy tried to NULL the
FK on photo delete instead of deleting the orphaned analysis row.
"""

from __future__ import annotations

import datetime
from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
from app.models.entry import Entry
from app.models.photo import Photo
from app.models.photo_analysis import PhotoAnalysis
from app.models.photo_ingredient import PhotoIngredient


@pytest.fixture
def db() -> Generator[Session, None, None]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _make_entry_with_analyzed_photo(db: Session) -> tuple[Entry, Photo]:
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
    db.commit()

    photo = Photo(
        entry_id=entry.id,
        filename="2026-05-15_photo-1.jpg",
        original_filename="lunch.jpg",
        created_at=datetime.datetime.utcnow(),
    )
    db.add(photo)
    db.commit()

    analysis = PhotoAnalysis(
        photo_id=photo.id,
        status="confirmed",
        dish_name="pasta carbonara",
        dish_confidence=0.92,
        model_id="google/gemini-3-flash-preview",
    )
    db.add(analysis)
    db.commit()

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
    db.commit()
    return entry, photo


def test_delete_photo_with_analysis_cascades(db: Session) -> None:
    """The exact production failure: deleting a Photo that has a
    PhotoAnalysis must NOT raise IntegrityError. The analysis row should
    be deleted along with the photo."""
    _, photo = _make_entry_with_analyzed_photo(db)
    photo_id = photo.id

    # Sanity: analysis + ingredients exist before delete
    assert db.query(PhotoAnalysis).filter_by(photo_id=photo_id).count() == 1
    assert (
        db.query(PhotoIngredient)
        .join(PhotoAnalysis)
        .filter(PhotoAnalysis.photo_id == photo_id)
        .count()
        == 2
    )

    db.delete(photo)
    db.commit()  # would raise IntegrityError without the cascade

    # Photo gone
    assert db.query(Photo).filter_by(id=photo_id).first() is None
    # Analysis cascaded
    assert db.query(PhotoAnalysis).filter_by(photo_id=photo_id).count() == 0
    # Ingredients cascaded through the analysis
    assert db.query(PhotoIngredient).count() == 0


def test_delete_photo_without_analysis_still_works(db: Session) -> None:
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
    db.add(entry)
    db.commit()
    photo = Photo(
        entry_id=entry.id,
        filename="x.jpg",
        created_at=datetime.datetime.utcnow(),
    )
    db.add(photo)
    db.commit()
    photo_id = photo.id

    db.delete(photo)
    db.commit()

    assert db.query(Photo).filter_by(id=photo_id).first() is None


def test_delete_entry_cascades_to_photo_and_analysis(db: Session) -> None:
    """Deleting an Entry should also wipe its photos and their analyses
    (Entry.photos already has cascade='all, delete-orphan')."""
    entry, _ = _make_entry_with_analyzed_photo(db)
    entry_id = entry.id

    db.delete(entry)
    db.commit()

    assert db.query(Entry).filter_by(id=entry_id).first() is None
    assert db.query(Photo).count() == 0
    assert db.query(PhotoAnalysis).count() == 0
    assert db.query(PhotoIngredient).count() == 0
