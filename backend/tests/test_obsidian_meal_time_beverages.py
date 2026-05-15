"""Tests for Phase 2 additions to the Obsidian vault renderer.

Covers:
- meal_time rendered as (HH:MM) inline with the photo embed
- meal_time=None produces no time suffix
- alcohol_units / caffeine_servings omit-when-zero in frontmatter and summary table
- Non-zero values produce the expected frontmatter keys AND had-* boolean
- Mixed case: one beverage > 0, the other zero
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
from app.services.obsidian import _render_markdown


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


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


def _make_entry(
    db: Session,
    *,
    date: datetime.date = datetime.date(2026, 5, 15),
    alcohol_units: int | None = None,
    caffeine_servings: int | None = None,
) -> Entry:
    entry = Entry(
        date=date,
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
        alcohol_units=alcohol_units,
        caffeine_servings=caffeine_servings,
    )
    db.add(entry)
    db.commit()
    return entry


def _make_photo(
    db: Session,
    entry: Entry,
    *,
    filename: str = "2026-05-15_photo-1.jpg",
    meal_time: datetime.datetime | None = None,
) -> Photo:
    photo = Photo(
        entry_id=entry.id,
        filename=filename,
        created_at=datetime.datetime(2026, 5, 15, 12, 0, 0),
        meal_time=meal_time,
    )
    db.add(photo)
    db.commit()
    return photo


# ---------------------------------------------------------------------------
# meal_time rendering
# ---------------------------------------------------------------------------


def test_photo_embed_includes_meal_time_hhmm(db: Session) -> None:
    """meal_time renders as (HH:MM) inline with the Obsidian embed wikilink."""
    entry = _make_entry(db)
    photo = _make_photo(
        db,
        entry,
        meal_time=datetime.datetime(2026, 5, 15, 13, 24, 0),
    )
    md = _render_markdown(db, entry, [photo])

    # The embed line must carry the time suffix.
    assert "![[attachments/2026-05-15_photo-1.jpg]] (13:24)" in md


def test_photo_embed_zero_padded_time(db: Session) -> None:
    """Single-digit hours and minutes must be zero-padded."""
    entry = _make_entry(db, date=datetime.date(2026, 5, 16))
    photo = _make_photo(
        db,
        entry,
        filename="2026-05-16_photo-1.jpg",
        meal_time=datetime.datetime(2026, 5, 16, 8, 5, 0),
    )
    md = _render_markdown(db, entry, [photo])

    assert "![[attachments/2026-05-16_photo-1.jpg]] (08:05)" in md


def test_photo_embed_no_time_when_meal_time_none(db: Session) -> None:
    """When meal_time is None no time suffix is appended — bare embed only."""
    entry = _make_entry(db, date=datetime.date(2026, 5, 17))
    photo = _make_photo(
        db,
        entry,
        filename="2026-05-17_photo-1.jpg",
        meal_time=None,
    )
    md = _render_markdown(db, entry, [photo])

    embed_line = next(
        (ln for ln in md.splitlines() if "2026-05-17_photo-1.jpg" in ln),
        None,
    )
    assert embed_line is not None
    # No time in parentheses after the embed.
    assert embed_line == "![[attachments/2026-05-17_photo-1.jpg]]"


# ---------------------------------------------------------------------------
# alcohol_units: frontmatter + summary table omit-when-zero
# ---------------------------------------------------------------------------


def test_alcohol_zero_omits_frontmatter_keys(db: Session) -> None:
    """alcohol_units=0 must not produce any alcohol-related frontmatter key."""
    entry = _make_entry(db, date=datetime.date(2026, 5, 20), alcohol_units=0)
    md = _render_markdown(db, entry, [])

    assert "alcohol-units" not in md
    assert "had-alcohol" not in md


def test_alcohol_none_omits_frontmatter_keys(db: Session) -> None:
    """alcohol_units=None (old rows) must not produce any alcohol-related key."""
    entry = _make_entry(db, date=datetime.date(2026, 5, 21), alcohol_units=None)
    md = _render_markdown(db, entry, [])

    assert "alcohol-units" not in md
    assert "had-alcohol" not in md


def test_alcohol_nonzero_emits_frontmatter_keys(db: Session) -> None:
    """alcohol_units=3 must produce alcohol-units: 3 AND had-alcohol: true in frontmatter."""
    entry = _make_entry(db, date=datetime.date(2026, 5, 22), alcohol_units=3)
    md = _render_markdown(db, entry, [])

    assert "alcohol-units: 3" in md
    assert "had-alcohol: true" in md


def test_alcohol_zero_omits_summary_table_row(db: Session) -> None:
    """alcohol_units=0 must not produce an Alcohol row in the summary table."""
    entry = _make_entry(db, date=datetime.date(2026, 5, 23), alcohol_units=0)
    md = _render_markdown(db, entry, [])

    assert "| Alcohol |" not in md


def test_alcohol_nonzero_emits_summary_table_row(db: Session) -> None:
    """alcohol_units=2 must produce a | Alcohol | row in the summary table."""
    entry = _make_entry(db, date=datetime.date(2026, 5, 24), alcohol_units=2)
    md = _render_markdown(db, entry, [])

    assert "| Alcohol | 2 unit(s) |" in md


# ---------------------------------------------------------------------------
# caffeine_servings: frontmatter + summary table omit-when-zero
# ---------------------------------------------------------------------------


def test_caffeine_zero_omits_frontmatter_keys(db: Session) -> None:
    entry = _make_entry(db, date=datetime.date(2026, 5, 25), caffeine_servings=0)
    md = _render_markdown(db, entry, [])

    assert "caffeine-servings" not in md
    assert "had-caffeine" not in md


def test_caffeine_none_omits_frontmatter_keys(db: Session) -> None:
    entry = _make_entry(db, date=datetime.date(2026, 5, 26), caffeine_servings=None)
    md = _render_markdown(db, entry, [])

    assert "caffeine-servings" not in md
    assert "had-caffeine" not in md


def test_caffeine_nonzero_emits_frontmatter_keys(db: Session) -> None:
    entry = _make_entry(db, date=datetime.date(2026, 5, 27), caffeine_servings=4)
    md = _render_markdown(db, entry, [])

    assert "caffeine-servings: 4" in md
    assert "had-caffeine: true" in md


def test_caffeine_zero_omits_summary_table_row(db: Session) -> None:
    entry = _make_entry(db, date=datetime.date(2026, 5, 28), caffeine_servings=0)
    md = _render_markdown(db, entry, [])

    assert "| Caffeine |" not in md


def test_caffeine_nonzero_emits_summary_table_row(db: Session) -> None:
    entry = _make_entry(db, date=datetime.date(2026, 5, 29), caffeine_servings=2)
    md = _render_markdown(db, entry, [])

    assert "| Caffeine | 2 serving(s) |" in md


# ---------------------------------------------------------------------------
# Mixed case: alcohol > 0, caffeine = 0 (and vice versa)
# ---------------------------------------------------------------------------


def test_mixed_alcohol_nonzero_caffeine_zero(db: Session) -> None:
    """Only alcohol keys appear; caffeine is fully absent."""
    entry = _make_entry(
        db,
        date=datetime.date(2026, 5, 30),
        alcohol_units=1,
        caffeine_servings=0,
    )
    md = _render_markdown(db, entry, [])

    assert "alcohol-units: 1" in md
    assert "had-alcohol: true" in md
    assert "caffeine-servings" not in md
    assert "had-caffeine" not in md
    assert "| Alcohol | 1 unit(s) |" in md
    assert "| Caffeine |" not in md


def test_mixed_caffeine_nonzero_alcohol_zero(db: Session) -> None:
    """Only caffeine keys appear; alcohol is fully absent."""
    entry = _make_entry(
        db,
        date=datetime.date(2026, 5, 31),
        alcohol_units=0,
        caffeine_servings=3,
    )
    md = _render_markdown(db, entry, [])

    assert "caffeine-servings: 3" in md
    assert "had-caffeine: true" in md
    assert "alcohol-units" not in md
    assert "had-alcohol" not in md
    assert "| Caffeine | 3 serving(s) |" in md
    assert "| Alcohol |" not in md
