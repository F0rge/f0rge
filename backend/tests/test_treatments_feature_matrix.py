from __future__ import annotations

import datetime
from collections.abc import Generator
from typing import Optional

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
from app.models.entry import Entry
from app.models.treatment import Treatment
from app.services.feature_matrix import build_feature_matrix


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


def _add_treatment(
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


def _add_entry(db: Session, date: datetime.date) -> Entry:
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
# Helpers
# ---------------------------------------------------------------------------


def _rows_by_date(rows: list[dict]) -> dict[str, dict]:
    return {r["date"]: r for r in rows}


# ---------------------------------------------------------------------------
# Single treatment over a 3-day range
# ---------------------------------------------------------------------------


def test_single_treatment_active_days(db: Session) -> None:
    """tx_allicin_active is True on all 3 days when treatment spans the range."""
    _add_treatment(db, "Allicin", "allicin", datetime.date(2026, 5, 1))

    rows, columns = build_feature_matrix(
        db,
        start_date=datetime.date(2026, 5, 13),
        end_date=datetime.date(2026, 5, 15),
    )

    assert "tx_allicin_active" in columns
    by_date = _rows_by_date(rows)
    assert by_date["2026-05-13"]["tx_allicin_active"] is True
    assert by_date["2026-05-14"]["tx_allicin_active"] is True
    assert by_date["2026-05-15"]["tx_allicin_active"] is True


def test_single_treatment_inactive_outside_range(db: Session) -> None:
    """Treatment that starts after the matrix range produces no tx_ column.

    build_feature_matrix pre-filters all_treatments to those overlapping
    [start_date, end_date], so a treatment fully outside the range is
    not represented in the column list at all.
    """
    _add_treatment(db, "Allicin", "allicin", datetime.date(2026, 6, 1))

    rows, columns = build_feature_matrix(
        db,
        start_date=datetime.date(2026, 5, 13),
        end_date=datetime.date(2026, 5, 15),
    )

    # Treatment is outside the range — no tx_ column generated
    tx_cols = [c for c in columns if c.startswith("tx_")]
    assert tx_cols == []


# ---------------------------------------------------------------------------
# Ongoing treatment (end_date=None)
# ---------------------------------------------------------------------------


def test_ongoing_treatment_active_through_end_of_range(db: Session) -> None:
    """Ongoing treatment (end_date=None) is active on every day in the range."""
    _add_treatment(db, "Allicin", "allicin", datetime.date(2026, 5, 1), end_date=None)

    rows, columns = build_feature_matrix(
        db,
        start_date=datetime.date(2026, 5, 13),
        end_date=datetime.date(2026, 5, 15),
    )

    by_date = _rows_by_date(rows)
    assert all(by_date[d]["tx_allicin_active"] is True for d in by_date)


# ---------------------------------------------------------------------------
# Multiple treatments → separate tx_ columns
# ---------------------------------------------------------------------------


def test_multiple_treatments_separate_columns(db: Session) -> None:
    """Each treatment gets its own tx_ column, sorted by normalized_name."""
    _add_treatment(db, "Rifaximin", "rifaximin", datetime.date(2026, 5, 1))
    _add_treatment(db, "Allicin", "allicin", datetime.date(2026, 5, 1))

    rows, columns = build_feature_matrix(
        db,
        start_date=datetime.date(2026, 5, 15),
        end_date=datetime.date(2026, 5, 15),
    )

    # Both columns present
    assert "tx_allicin_active" in columns
    assert "tx_rifaximin_active" in columns

    # tx_ columns sorted by normalized_name: allicin before rifaximin
    tx_cols = [c for c in columns if c.startswith("tx_")]
    assert tx_cols.index("tx_allicin_active") < tx_cols.index("tx_rifaximin_active")

    row = rows[0]
    assert row["tx_allicin_active"] is True
    assert row["tx_rifaximin_active"] is True


def test_multiple_treatments_only_active_one_marked(db: Session) -> None:
    """Only the treatment overlapping the range appears in columns.

    An expired treatment wholly outside [start_date, end_date] is excluded
    from all_treatments and gets no column. Only the currently-active one
    produces a tx_ column, and it is True.
    """
    # Allicin: ended April 30 — entirely before the May 15 range
    _add_treatment(
        db,
        "Allicin",
        "allicin",
        datetime.date(2026, 4, 1),
        datetime.date(2026, 4, 30),
    )
    # Rifaximin: active during range
    _add_treatment(db, "Rifaximin", "rifaximin", datetime.date(2026, 5, 1))

    rows, columns = build_feature_matrix(
        db,
        start_date=datetime.date(2026, 5, 15),
        end_date=datetime.date(2026, 5, 15),
    )

    # Allicin is outside range — no column for it
    assert "tx_allicin_active" not in columns
    # Rifaximin overlaps — column present and True
    assert "tx_rifaximin_active" in columns
    assert rows[0]["tx_rifaximin_active"] is True


# ---------------------------------------------------------------------------
# No treatments → no tx_ columns
# ---------------------------------------------------------------------------


def test_no_treatments_no_tx_columns(db: Session) -> None:
    _add_entry(db, datetime.date(2026, 5, 15))

    rows, columns = build_feature_matrix(
        db,
        start_date=datetime.date(2026, 5, 15),
        end_date=datetime.date(2026, 5, 15),
    )

    tx_cols = [c for c in columns if c.startswith("tx_")]
    assert tx_cols == []


# ---------------------------------------------------------------------------
# Boundary: start_date and end_date inclusivity
# ---------------------------------------------------------------------------


def test_boundary_active_on_start_date(db: Session) -> None:
    """First day of treatment is active (start_date is inclusive)."""
    _add_treatment(
        db,
        "Allicin",
        "allicin",
        datetime.date(2026, 5, 15),
        datetime.date(2026, 5, 31),
    )

    rows, _ = build_feature_matrix(
        db,
        start_date=datetime.date(2026, 5, 15),
        end_date=datetime.date(2026, 5, 15),
    )

    assert rows[0]["tx_allicin_active"] is True


def test_boundary_day_before_start_is_false(db: Session) -> None:
    """Day before treatment starts: treatment doesn't overlap the range at all.

    build_feature_matrix filters treatments by overlap with [start, end].
    A treatment starting on May 15 does not overlap a range of May 14–14,
    so no tx_ column is produced.
    """
    _add_treatment(
        db,
        "Allicin",
        "allicin",
        datetime.date(2026, 5, 15),
    )

    rows, columns = build_feature_matrix(
        db,
        start_date=datetime.date(2026, 5, 14),
        end_date=datetime.date(2026, 5, 14),
    )

    # Treatment start is after the range end — no column generated
    tx_cols = [c for c in columns if c.startswith("tx_")]
    assert tx_cols == []


def test_boundary_active_on_end_date(db: Session) -> None:
    """Last day of treatment is active (end_date is inclusive)."""
    _add_treatment(
        db,
        "Allicin",
        "allicin",
        datetime.date(2026, 5, 1),
        datetime.date(2026, 5, 15),
    )

    rows, _ = build_feature_matrix(
        db,
        start_date=datetime.date(2026, 5, 15),
        end_date=datetime.date(2026, 5, 15),
    )

    assert rows[0]["tx_allicin_active"] is True


def test_boundary_day_after_end_is_false(db: Session) -> None:
    """Day after treatment ends: treatment doesn't overlap the range.

    A treatment ending on May 15 does not overlap a range of May 16–16,
    so no tx_ column is produced.
    """
    _add_treatment(
        db,
        "Allicin",
        "allicin",
        datetime.date(2026, 5, 1),
        datetime.date(2026, 5, 15),
    )

    rows, columns = build_feature_matrix(
        db,
        start_date=datetime.date(2026, 5, 16),
        end_date=datetime.date(2026, 5, 16),
    )

    # Treatment end is before range start — no column generated
    tx_cols = [c for c in columns if c.startswith("tx_")]
    assert tx_cols == []


# ---------------------------------------------------------------------------
# Multi-day range with partial coverage
# ---------------------------------------------------------------------------


def test_partial_range_coverage(db: Session) -> None:
    """Treatment covering only some days in range has mixed True/False."""
    _add_treatment(
        db,
        "Allicin",
        "allicin",
        datetime.date(2026, 5, 14),
        datetime.date(2026, 5, 15),
    )

    rows, _ = build_feature_matrix(
        db,
        start_date=datetime.date(2026, 5, 13),
        end_date=datetime.date(2026, 5, 16),
    )

    by_date = _rows_by_date(rows)
    assert by_date["2026-05-13"]["tx_allicin_active"] is False
    assert by_date["2026-05-14"]["tx_allicin_active"] is True
    assert by_date["2026-05-15"]["tx_allicin_active"] is True
    assert by_date["2026-05-16"]["tx_allicin_active"] is False
