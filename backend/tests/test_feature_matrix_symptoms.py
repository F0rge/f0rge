from __future__ import annotations

import datetime
from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
from app.models.entry import Entry
from app.models.symptom_catalog import SymptomCatalogItem
from app.services.feature_matrix import STATIC_COLUMNS, build_feature_matrix


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


def _add_entry(
    db: Session,
    date: datetime.date,
    symptoms_json: dict | None = None,
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


def _add_sym_item(
    db: Session,
    key: str,
    label: str,
    archived: bool = False,
    first_used_at: datetime.datetime | None = None,
) -> SymptomCatalogItem:
    item = SymptomCatalogItem(
        key=key,
        label=label,
        archived=archived,
        sort_order=0,
        first_used_at=first_used_at,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


_DATE = datetime.date(2026, 5, 15)
_NOW = datetime.datetime(2026, 5, 15, 12, 0, 0)


# ---------------------------------------------------------------------------
# No entries → no sym_* columns
# ---------------------------------------------------------------------------


def test_no_entries_no_sym_columns(db: Session) -> None:
    rows, columns = build_feature_matrix(db, _DATE, _DATE)
    sym_cols = [c for c in columns if c.startswith("sym_")]
    assert sym_cols == []


# ---------------------------------------------------------------------------
# Entry with vss → sym_vss column appears with correct value
# ---------------------------------------------------------------------------


def test_entry_with_symptom_creates_column(db: Session) -> None:
    _add_sym_item(db, "vss", "Visual Snow", first_used_at=_NOW)
    _add_entry(db, _DATE, {"vss": 7})

    rows, columns = build_feature_matrix(db, _DATE, _DATE)
    assert "sym_vss" in columns
    assert rows[0]["sym_vss"] == 7


# ---------------------------------------------------------------------------
# Other dates get None for sym_* value
# ---------------------------------------------------------------------------


def test_other_dates_get_none_for_symptom(db: Session) -> None:
    _add_sym_item(db, "vss", "Visual Snow", first_used_at=_NOW)
    _add_entry(db, _DATE, {"vss": 7})
    other_date = _DATE - datetime.timedelta(days=1)
    _add_entry(db, other_date, {})

    rows, columns = build_feature_matrix(db, other_date, _DATE)
    by_date = {r["date"]: r for r in rows}
    assert by_date[other_date.isoformat()]["sym_vss"] is None
    assert by_date[_DATE.isoformat()]["sym_vss"] == 7


# ---------------------------------------------------------------------------
# Archived symptom is excluded even with historical first_used_at
# ---------------------------------------------------------------------------


def test_archived_symptom_excluded_from_columns(db: Session) -> None:
    _add_sym_item(db, "vss", "Visual Snow", archived=True, first_used_at=_NOW)
    _add_entry(db, _DATE, {"vss": 7})

    rows, columns = build_feature_matrix(db, _DATE, _DATE)
    sym_cols = [c for c in columns if c.startswith("sym_")]
    assert sym_cols == []


# ---------------------------------------------------------------------------
# Column ordering: STATIC + supp_* + tx_* + sym_*
# ---------------------------------------------------------------------------


def test_column_order_static_then_supp_then_tx_then_sym(db: Session) -> None:
    _add_sym_item(db, "tinnitus", "Tinnitus", first_used_at=_NOW)
    _add_entry(db, _DATE, {"tinnitus": 5})

    rows, columns = build_feature_matrix(db, _DATE, _DATE)

    supp_cols = [c for c in columns if c.startswith("supp_")]
    tx_cols = [c for c in columns if c.startswith("tx_")]
    sym_cols = [c for c in columns if c.startswith("sym_")]

    # Build expected ordering: static then supp then tx then sym
    expected_tail = supp_cols + tx_cols + sym_cols
    actual_tail = [c for c in columns if c not in STATIC_COLUMNS]
    assert actual_tail == expected_tail

    # sym_* comes after all tx_* columns
    if sym_cols and tx_cols:
        last_tx_idx = max(columns.index(c) for c in tx_cols)
        first_sym_idx = min(columns.index(c) for c in sym_cols)
        assert first_sym_idx > last_tx_idx
