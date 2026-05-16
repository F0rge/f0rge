from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entry import Entry
from app.models.treatment import Treatment
from app.services.feature_matrix import build_feature_matrix


async def _add_treatment(
    db: AsyncSession,
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
    await db.commit()
    await db.refresh(t)
    return t


async def _add_entry(db: AsyncSession, date: datetime.date) -> Entry:
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
    await db.commit()
    await db.refresh(entry)
    return entry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _rows_by_date(rows: list[dict]) -> dict[str, dict]:
    return {r["date"]: r for r in rows}


# ---------------------------------------------------------------------------
# Single treatment over a 3-day range
# ---------------------------------------------------------------------------


async def test_single_treatment_active_days(async_db: AsyncSession) -> None:
    """tx_allicin_active is True on all 3 days when treatment spans the range."""
    await _add_treatment(async_db, "Allicin", "allicin", datetime.date(2026, 5, 1))

    rows, columns = await build_feature_matrix(
        async_db,
        start_date=datetime.date(2026, 5, 13),
        end_date=datetime.date(2026, 5, 15),
    )

    assert "tx_allicin_active" in columns
    by_date = _rows_by_date(rows)
    assert by_date["2026-05-13"]["tx_allicin_active"] is True
    assert by_date["2026-05-14"]["tx_allicin_active"] is True
    assert by_date["2026-05-15"]["tx_allicin_active"] is True


async def test_single_treatment_inactive_outside_range(
    async_db: AsyncSession,
) -> None:
    """Treatment that starts after the matrix range produces no tx_ column."""
    await _add_treatment(async_db, "Allicin", "allicin", datetime.date(2026, 6, 1))

    rows, columns = await build_feature_matrix(
        async_db,
        start_date=datetime.date(2026, 5, 13),
        end_date=datetime.date(2026, 5, 15),
    )

    # Treatment is outside the range — no tx_ column generated
    tx_cols = [c for c in columns if c.startswith("tx_")]
    assert tx_cols == []


# ---------------------------------------------------------------------------
# Ongoing treatment (end_date=None)
# ---------------------------------------------------------------------------


async def test_ongoing_treatment_active_through_end_of_range(
    async_db: AsyncSession,
) -> None:
    """Ongoing treatment (end_date=None) is active on every day in the range."""
    await _add_treatment(
        async_db, "Allicin", "allicin", datetime.date(2026, 5, 1), end_date=None
    )

    rows, columns = await build_feature_matrix(
        async_db,
        start_date=datetime.date(2026, 5, 13),
        end_date=datetime.date(2026, 5, 15),
    )

    by_date = _rows_by_date(rows)
    assert all(by_date[d]["tx_allicin_active"] is True for d in by_date)


# ---------------------------------------------------------------------------
# Multiple treatments → separate tx_ columns
# ---------------------------------------------------------------------------


async def test_multiple_treatments_separate_columns(async_db: AsyncSession) -> None:
    """Each treatment gets its own tx_ column, sorted by normalized_name."""
    await _add_treatment(
        async_db, "Rifaximin", "rifaximin", datetime.date(2026, 5, 1)
    )
    await _add_treatment(async_db, "Allicin", "allicin", datetime.date(2026, 5, 1))

    rows, columns = await build_feature_matrix(
        async_db,
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


async def test_multiple_treatments_only_active_one_marked(
    async_db: AsyncSession,
) -> None:
    """Only the treatment overlapping the range appears in columns."""
    # Allicin: ended April 30 — entirely before the May 15 range
    await _add_treatment(
        async_db,
        "Allicin",
        "allicin",
        datetime.date(2026, 4, 1),
        datetime.date(2026, 4, 30),
    )
    # Rifaximin: active during range
    await _add_treatment(
        async_db, "Rifaximin", "rifaximin", datetime.date(2026, 5, 1)
    )

    rows, columns = await build_feature_matrix(
        async_db,
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


async def test_no_treatments_no_tx_columns(async_db: AsyncSession) -> None:
    await _add_entry(async_db, datetime.date(2026, 5, 15))

    rows, columns = await build_feature_matrix(
        async_db,
        start_date=datetime.date(2026, 5, 15),
        end_date=datetime.date(2026, 5, 15),
    )

    tx_cols = [c for c in columns if c.startswith("tx_")]
    assert tx_cols == []


# ---------------------------------------------------------------------------
# Boundary: start_date and end_date inclusivity
# ---------------------------------------------------------------------------


async def test_boundary_active_on_start_date(async_db: AsyncSession) -> None:
    """First day of treatment is active (start_date is inclusive)."""
    await _add_treatment(
        async_db,
        "Allicin",
        "allicin",
        datetime.date(2026, 5, 15),
        datetime.date(2026, 5, 31),
    )

    rows, _ = await build_feature_matrix(
        async_db,
        start_date=datetime.date(2026, 5, 15),
        end_date=datetime.date(2026, 5, 15),
    )

    assert rows[0]["tx_allicin_active"] is True


async def test_boundary_day_before_start_is_false(async_db: AsyncSession) -> None:
    """Day before treatment starts: treatment doesn't overlap the range at all."""
    await _add_treatment(
        async_db,
        "Allicin",
        "allicin",
        datetime.date(2026, 5, 15),
    )

    rows, columns = await build_feature_matrix(
        async_db,
        start_date=datetime.date(2026, 5, 14),
        end_date=datetime.date(2026, 5, 14),
    )

    # Treatment start is after the range end — no column generated
    tx_cols = [c for c in columns if c.startswith("tx_")]
    assert tx_cols == []


async def test_boundary_active_on_end_date(async_db: AsyncSession) -> None:
    """Last day of treatment is active (end_date is inclusive)."""
    await _add_treatment(
        async_db,
        "Allicin",
        "allicin",
        datetime.date(2026, 5, 1),
        datetime.date(2026, 5, 15),
    )

    rows, _ = await build_feature_matrix(
        async_db,
        start_date=datetime.date(2026, 5, 15),
        end_date=datetime.date(2026, 5, 15),
    )

    assert rows[0]["tx_allicin_active"] is True


async def test_boundary_day_after_end_is_false(async_db: AsyncSession) -> None:
    """Day after treatment ends: treatment doesn't overlap the range."""
    await _add_treatment(
        async_db,
        "Allicin",
        "allicin",
        datetime.date(2026, 5, 1),
        datetime.date(2026, 5, 15),
    )

    rows, columns = await build_feature_matrix(
        async_db,
        start_date=datetime.date(2026, 5, 16),
        end_date=datetime.date(2026, 5, 16),
    )

    # Treatment end is before range start — no column generated
    tx_cols = [c for c in columns if c.startswith("tx_")]
    assert tx_cols == []


# ---------------------------------------------------------------------------
# Multi-day range with partial coverage
# ---------------------------------------------------------------------------


async def test_partial_range_coverage(async_db: AsyncSession) -> None:
    """Treatment covering only some days in range has mixed True/False."""
    await _add_treatment(
        async_db,
        "Allicin",
        "allicin",
        datetime.date(2026, 5, 14),
        datetime.date(2026, 5, 15),
    )

    rows, _ = await build_feature_matrix(
        async_db,
        start_date=datetime.date(2026, 5, 13),
        end_date=datetime.date(2026, 5, 16),
    )

    by_date = _rows_by_date(rows)
    assert by_date["2026-05-13"]["tx_allicin_active"] is False
    assert by_date["2026-05-14"]["tx_allicin_active"] is True
    assert by_date["2026-05-15"]["tx_allicin_active"] is True
    assert by_date["2026-05-16"]["tx_allicin_active"] is False
