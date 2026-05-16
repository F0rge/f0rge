from __future__ import annotations

import datetime
from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
from app.models.entry import Entry
from app.models.symptom_catalog import SymptomCatalogItem
from app.services.obsidian import _render_markdown


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


def _make_entry(db: Session, symptoms_json: dict | None = None) -> Entry:
    entry = Entry(
        date=datetime.date(2026, 5, 15),
        schema_version=3,
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
        symptoms_json=symptoms_json if symptoms_json is not None else {},
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def _add_catalog_item(
    db: Session, key: str, label: str, archived: bool = False
) -> SymptomCatalogItem:
    item = SymptomCatalogItem(
        key=key,
        label=label,
        archived=archived,
        sort_order=0,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


# ---------------------------------------------------------------------------
# Empty symptoms
# ---------------------------------------------------------------------------


def test_empty_symptoms_frontmatter(db: Session) -> None:
    entry = _make_entry(db, {})
    md = _render_markdown(db, entry, [])
    assert "symptoms-count: 0" in md
    # No sym-* lines should appear
    assert "sym-" not in md


def test_empty_symptoms_summary_row(db: Session) -> None:
    entry = _make_entry(db, {})
    md = _render_markdown(db, entry, [])
    assert "| Symptoms | None today |" in md


# ---------------------------------------------------------------------------
# Active symptoms render correctly
# ---------------------------------------------------------------------------


def test_active_symptoms_frontmatter(db: Session) -> None:
    _add_catalog_item(db, "tinnitus", "Tinnitus")
    _add_catalog_item(db, "vss", "Visual Snow")
    entry = _make_entry(db, {"vss": 7, "tinnitus": 6})
    md = _render_markdown(db, entry, [])

    assert "sym-tinnitus: 6" in md
    assert "sym-vss: 7" in md
    assert "symptoms-count: 2" in md


def test_active_symptoms_sorted_in_frontmatter(db: Session) -> None:
    """sym-* lines appear in alphabetical key order."""
    _add_catalog_item(db, "tinnitus", "Tinnitus")
    _add_catalog_item(db, "vss", "Visual Snow")
    entry = _make_entry(db, {"vss": 7, "tinnitus": 6})
    md = _render_markdown(db, entry, [])

    tinnitus_pos = md.index("sym-tinnitus:")
    vss_pos = md.index("sym-vss:")
    assert tinnitus_pos < vss_pos


def test_active_symptoms_summary_row(db: Session) -> None:
    _add_catalog_item(db, "tinnitus", "Tinnitus")
    _add_catalog_item(db, "vss", "Visual Snow")
    entry = _make_entry(db, {"vss": 7, "tinnitus": 6})
    md = _render_markdown(db, entry, [])

    # Both labels must appear in the summary row
    assert "Tinnitus 6/10" in md
    assert "Visual Snow 7/10" in md


# ---------------------------------------------------------------------------
# Archived symptoms are excluded
# ---------------------------------------------------------------------------


def test_archived_symptom_excluded_from_frontmatter(db: Session) -> None:
    _add_catalog_item(db, "vss", "Visual Snow", archived=True)
    entry = _make_entry(db, {"vss": 7})
    md = _render_markdown(db, entry, [])

    assert "sym-vss" not in md
    assert "symptoms-count: 0" in md


def test_archived_symptom_summary_says_none_today(db: Session) -> None:
    _add_catalog_item(db, "vss", "Visual Snow", archived=True)
    entry = _make_entry(db, {"vss": 7})
    md = _render_markdown(db, entry, [])
    assert "| Symptoms | None today |" in md
