from __future__ import annotations

import datetime
import tempfile
from collections.abc import Generator
from typing import Optional

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
from app.models.entry import Entry
from app.models.treatment import Treatment
from app.services.obsidian import _format_active_treatments, _render_markdown


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


def _make_treatment(
    db: Session,
    name: str,
    normalized_name: str,
    start_date: datetime.date,
    end_date: Optional[datetime.date] = None,
) -> Treatment:
    t = Treatment(
        name=name,
        normalized_name=normalized_name,
        type="antimicrobial",
        start_date=start_date,
        end_date=end_date,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


def _make_entry(db: Session, date: datetime.date) -> Entry:
    entry = Entry(
        date=date,
        schema_version=2,
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
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


# ---------------------------------------------------------------------------
# _format_active_treatments
# ---------------------------------------------------------------------------


def test_format_empty_list() -> None:
    assert _format_active_treatments([], datetime.date(2026, 5, 15)) == "None"


def test_format_single_treatment_day_1() -> None:
    t = Treatment(
        name="Allicin",
        normalized_name="allicin",
        type="antimicrobial",
        start_date=datetime.date(2026, 5, 15),
    )
    result = _format_active_treatments([t], datetime.date(2026, 5, 15))
    assert result == "Allicin (day 1)"


def test_format_day_count_start_is_day_1() -> None:
    """Day count: (as_of - start_date).days + 1 — start day is day 1 not day 0."""
    t = Treatment(
        name="Rifaximin",
        normalized_name="rifaximin",
        type="antibiotic",
        start_date=datetime.date(2026, 5, 1),
    )
    # 14 days later → day 15
    as_of = datetime.date(2026, 5, 15)
    result = _format_active_treatments([t], as_of)
    assert result == "Rifaximin (day 15)"


def test_format_multiple_treatments() -> None:
    allicin = Treatment(
        name="Allicin",
        normalized_name="allicin",
        type="antimicrobial",
        start_date=datetime.date(2026, 5, 8),
    )
    rifaximin = Treatment(
        name="Rifaximin",
        normalized_name="rifaximin",
        type="antibiotic",
        start_date=datetime.date(2026, 5, 13),
    )
    as_of = datetime.date(2026, 5, 15)
    result = _format_active_treatments([allicin, rifaximin], as_of)
    # allicin: day 8, rifaximin: day 3
    assert result == "Allicin (day 8), Rifaximin (day 3)"


# ---------------------------------------------------------------------------
# _render_markdown — frontmatter and table
# ---------------------------------------------------------------------------


@pytest.fixture
def vault_dir() -> Generator[str, None, None]:
    with tempfile.TemporaryDirectory() as tmp:
        yield tmp


def test_render_markdown_with_active_treatment(
    db: Session,
    vault_dir: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """active-treatments frontmatter and summary table row are written correctly."""
    monkeypatch.setattr("app.services.obsidian.settings.vault_path", vault_dir)
    monkeypatch.setattr(
        "app.services.obsidian.get_daily_summary",
        lambda db, date: None,
    )

    entry_date = datetime.date(2026, 5, 15)
    entry = _make_entry(db, entry_date)
    _make_treatment(db, "Allicin", "allicin", datetime.date(2026, 5, 8))

    content = _render_markdown(db, entry, [])

    # Frontmatter: normalized_name appears in the list
    assert "active-treatments: [allicin]" in content
    # Summary table row
    assert "| Active treatments | Allicin (day 8) |" in content


def test_render_markdown_no_active_treatment(
    db: Session,
    vault_dir: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With no treatments, frontmatter list is empty and table row shows None."""
    monkeypatch.setattr("app.services.obsidian.settings.vault_path", vault_dir)
    monkeypatch.setattr(
        "app.services.obsidian.get_daily_summary",
        lambda db, date: None,
    )

    entry_date = datetime.date(2026, 5, 15)
    entry = _make_entry(db, entry_date)

    content = _render_markdown(db, entry, [])

    assert "active-treatments: []" in content
    assert "| Active treatments | None |" in content


def test_render_markdown_multiple_treatments(
    db: Session,
    vault_dir: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Multiple active treatments all appear in frontmatter and table."""
    monkeypatch.setattr("app.services.obsidian.settings.vault_path", vault_dir)
    monkeypatch.setattr(
        "app.services.obsidian.get_daily_summary",
        lambda db, date: None,
    )

    entry_date = datetime.date(2026, 5, 15)
    entry = _make_entry(db, entry_date)
    # Both are active on entry_date
    _make_treatment(db, "Allicin", "allicin", datetime.date(2026, 5, 8))
    _make_treatment(db, "Rifaximin", "rifaximin", datetime.date(2026, 5, 13))

    content = _render_markdown(db, entry, [])

    # The obsidian service orders by Treatment.name
    assert "active-treatments: [allicin, rifaximin]" in content
    assert "Allicin (day 8)" in content
    assert "Rifaximin (day 3)" in content


def test_render_markdown_expired_treatment_excluded(
    db: Session,
    vault_dir: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Treatment that ended before the entry date must not appear."""
    monkeypatch.setattr("app.services.obsidian.settings.vault_path", vault_dir)
    monkeypatch.setattr(
        "app.services.obsidian.get_daily_summary",
        lambda db, date: None,
    )

    entry_date = datetime.date(2026, 5, 15)
    entry = _make_entry(db, entry_date)
    # Ended on May 14 — one day before entry
    _make_treatment(
        db,
        "OldDrug",
        "olddrug",
        datetime.date(2026, 5, 1),
        datetime.date(2026, 5, 14),
    )

    content = _render_markdown(db, entry, [])

    assert "active-treatments: []" in content
    assert "OldDrug" not in content


def test_render_markdown_treatment_active_on_last_day(
    db: Session,
    vault_dir: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Treatment ending on the exact entry date is still active (inclusive)."""
    monkeypatch.setattr("app.services.obsidian.settings.vault_path", vault_dir)
    monkeypatch.setattr(
        "app.services.obsidian.get_daily_summary",
        lambda db, date: None,
    )

    entry_date = datetime.date(2026, 5, 15)
    entry = _make_entry(db, entry_date)
    _make_treatment(
        db,
        "Berberine",
        "berberine",
        datetime.date(2026, 5, 1),
        datetime.date(2026, 5, 15),  # ends today — still active
    )

    content = _render_markdown(db, entry, [])

    assert "active-treatments: [berberine]" in content
    assert "Berberine (day 15)" in content
