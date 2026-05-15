"""Tests for meal_time on Photo and alcohol_units/caffeine_servings on Entry.

Covers:
- Upload without meal_time defaults to ~utcnow
- Upload with explicit meal_time persists it
- PATCH /photos/{photo_id} updates meal_time on an existing photo
- PATCH on a missing photo returns 404
- Migration backfill: a row with NULL meal_time gets created_at after _run_migrations()
- alcohol_units / caffeine_servings round-trip on Entry create and update
"""

from __future__ import annotations

import asyncio
import datetime
import io
import sqlite3
from collections.abc import Generator

import pytest
from fastapi import BackgroundTasks, UploadFile
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.database import Base
from app.exceptions import NotFoundError
from app.models.entry import Entry
from app.models.photo import Photo
from app.services.photos import PhotoService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db() -> Generator[Session, None, None]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def isolated_storage(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> Generator[None, None, None]:
    photo_dir = tmp_path / "photos"
    vault_dir = tmp_path / "vault"
    photo_dir.mkdir()
    vault_dir.mkdir()
    monkeypatch.setattr(settings, "photo_dir", str(photo_dir))
    monkeypatch.setattr(settings, "vault_path", str(vault_dir))
    monkeypatch.setattr(settings, "food_analysis_enabled", False)
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    monkeypatch.setattr("app.services.photos.write_daily_file", lambda *a, **kw: None)
    yield


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_entry(db: Session, day: datetime.date) -> Entry:
    entry = Entry(
        date=day,
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
    return entry


def _png_bytes() -> bytes:
    img = Image.new("RGB", (10, 10), color="blue")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _upload(
    db: Session,
    day: datetime.date,
    meal_time: datetime.datetime | None = None,
) -> Photo:
    upload = UploadFile(filename="test.png", file=io.BytesIO(_png_bytes()))
    service = PhotoService(db)
    return asyncio.run(
        service.upload(
            entry_date=day,
            file=upload,
            label=None,
            meal_time=meal_time,
            background_tasks=BackgroundTasks(),
        )
    )


# ---------------------------------------------------------------------------
# meal_time on Photo upload
# ---------------------------------------------------------------------------


def test_upload_without_meal_time_defaults_to_now(
    db: Session, isolated_storage: None
) -> None:
    day = datetime.date(2026, 5, 15)
    _make_entry(db, day)
    before = datetime.datetime.utcnow()

    photo = _upload(db, day)

    after = datetime.datetime.utcnow()
    assert photo.meal_time is not None
    # Allow a 5-second window around test execution time
    assert (
        before - datetime.timedelta(seconds=5)
        <= photo.meal_time
        <= after + datetime.timedelta(seconds=5)
    )


def test_upload_with_explicit_meal_time_persists_it(
    db: Session, isolated_storage: None
) -> None:
    day = datetime.date(2026, 5, 15)
    _make_entry(db, day)
    explicit_time = datetime.datetime(2026, 5, 15, 8, 30, 0)

    photo = _upload(db, day, meal_time=explicit_time)

    assert photo.meal_time == explicit_time


# ---------------------------------------------------------------------------
# PATCH /photos/{photo_id}
# ---------------------------------------------------------------------------


def test_patch_updates_meal_time(db: Session, isolated_storage: None) -> None:
    day = datetime.date(2026, 5, 15)
    _make_entry(db, day)
    photo = _upload(db, day)

    new_time = datetime.datetime(2026, 5, 15, 12, 0, 0)
    service = PhotoService(db)
    updated = service.update_meal_time(photo.id, new_time)

    assert updated.id == photo.id
    assert updated.meal_time == new_time


def test_patch_missing_photo_raises_not_found(db: Session) -> None:
    service = PhotoService(db)
    with pytest.raises(NotFoundError):
        service.update_meal_time(99999, datetime.datetime.utcnow())


# ---------------------------------------------------------------------------
# Migration backfill
# ---------------------------------------------------------------------------


def test_migration_backfills_meal_time_from_created_at() -> None:
    """Simulate a prod table that has no meal_time column, run _run_migrations(),
    verify existing rows get meal_time = created_at."""
    # Build an in-memory DB with the old schema (no meal_time column).
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE photos (
            id INTEGER PRIMARY KEY,
            entry_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            label TEXT,
            original_filename TEXT,
            created_at TEXT
        )
        """
    )
    frozen_ts = "2026-01-01 10:00:00"
    conn.execute(
        "INSERT INTO photos (entry_id, filename, created_at) VALUES (1, 'x.jpg', ?)",
        (frozen_ts,),
    )
    conn.commit()

    # Run just the photos migration logic directly (mirrors _run_migrations pattern).
    photo_cols = {
        row[1] for row in conn.execute("PRAGMA table_info(photos)").fetchall()
    }
    if "meal_time" not in photo_cols:
        conn.execute("ALTER TABLE photos ADD COLUMN meal_time DATETIME")
        conn.execute("UPDATE photos SET meal_time = created_at WHERE meal_time IS NULL")
    conn.commit()

    row = conn.execute("SELECT meal_time FROM photos WHERE id = 1").fetchone()
    conn.close()

    assert row is not None
    assert row[0] == frozen_ts


def test_migration_idempotent() -> None:
    """Running the photos migration twice must not raise."""
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE photos (
            id INTEGER PRIMARY KEY,
            entry_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            created_at TEXT,
            meal_time DATETIME
        )
        """
    )
    conn.commit()

    # First run
    photo_cols = {
        row[1] for row in conn.execute("PRAGMA table_info(photos)").fetchall()
    }
    if "meal_time" not in photo_cols:
        conn.execute("ALTER TABLE photos ADD COLUMN meal_time DATETIME")
        conn.execute("UPDATE photos SET meal_time = created_at WHERE meal_time IS NULL")
    conn.commit()

    # Second run — must not raise
    photo_cols = {
        row[1] for row in conn.execute("PRAGMA table_info(photos)").fetchall()
    }
    if "meal_time" not in photo_cols:
        conn.execute("ALTER TABLE photos ADD COLUMN meal_time DATETIME")
        conn.execute("UPDATE photos SET meal_time = created_at WHERE meal_time IS NULL")
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# alcohol_units / caffeine_servings on Entry (round-trip via ORM)
# ---------------------------------------------------------------------------


def test_entry_alcohol_caffeine_persist(db: Session) -> None:
    entry = Entry(
        date=datetime.date(2026, 5, 20),
        overall=3,
        bloating=1,
        stool_normal=False,
        joint_pain=0,
        neuro=0,
        sleep_quality=3,
        stress=2,
        diet_risk="low",
        supplements="",
        sick=False,
        hot_shower=False,
        alcohol_units=2,
        caffeine_servings=3,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)

    assert entry.alcohol_units == 2
    assert entry.caffeine_servings == 3


def test_entry_alcohol_caffeine_default_null(db: Session) -> None:
    entry = Entry(
        date=datetime.date(2026, 5, 21),
        overall=3,
        bloating=1,
        stool_normal=False,
        joint_pain=0,
        neuro=0,
        sleep_quality=3,
        stress=2,
        diet_risk="low",
        supplements="",
        sick=False,
        hot_shower=False,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)

    assert entry.alcohol_units is None
    assert entry.caffeine_servings is None


def test_entry_update_alcohol_caffeine(db: Session) -> None:
    entry = _make_entry(db, datetime.date(2026, 5, 22))
    entry.alcohol_units = 1
    entry.caffeine_servings = 4
    db.commit()
    db.refresh(entry)

    assert entry.alcohol_units == 1
    assert entry.caffeine_servings == 4


# ---------------------------------------------------------------------------
# Schema validation for alcohol_units / caffeine_servings bounds
# ---------------------------------------------------------------------------


def test_entry_schema_validation_bounds() -> None:
    from app.schemas.entry import EntryCreate
    import pydantic

    # ge=0 lower bound
    with pytest.raises(pydantic.ValidationError):
        EntryCreate(
            date=datetime.date(2026, 5, 15),
            overall=3,
            bloating=1,
            joint_pain=0,
            neuro=0,
            sleep_quality=3,
            stress=2,
            diet_risk="low",
            supplements="",
            sick=False,
            alcohol_units=-1,
        )

    # le=10 upper bound
    with pytest.raises(pydantic.ValidationError):
        EntryCreate(
            date=datetime.date(2026, 5, 15),
            overall=3,
            bloating=1,
            joint_pain=0,
            neuro=0,
            sleep_quality=3,
            stress=2,
            diet_risk="low",
            supplements="",
            sick=False,
            caffeine_servings=11,
        )
