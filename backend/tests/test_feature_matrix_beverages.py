from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entry import Entry
from app.services.feature_matrix import STATIC_COLUMNS, build_feature_matrix


async def _add_entry(
    db: AsyncSession,
    date: datetime.date,
    alcohol_units: Optional[int] = None,
    caffeine_servings: Optional[int] = None,
) -> Entry:
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
        alcohol_units=alcohol_units,
        caffeine_servings=caffeine_servings,
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry


_DATE = datetime.date(2026, 5, 15)


# ---------------------------------------------------------------------------
# alcohol_units raw column
# ---------------------------------------------------------------------------


async def test_alcohol_units_present_when_nonzero(async_db: AsyncSession) -> None:
    await _add_entry(async_db, _DATE, alcohol_units=3)
    rows, columns = await build_feature_matrix(
        async_db, start_date=_DATE, end_date=_DATE
    )

    assert "alcohol_units" in columns
    assert rows[0]["alcohol_units"] == 3


async def test_alcohol_units_zero(async_db: AsyncSession) -> None:
    await _add_entry(async_db, _DATE, alcohol_units=0)
    rows, columns = await build_feature_matrix(
        async_db, start_date=_DATE, end_date=_DATE
    )

    assert rows[0]["alcohol_units"] == 0


async def test_alcohol_units_none(async_db: AsyncSession) -> None:
    await _add_entry(async_db, _DATE, alcohol_units=None)
    rows, columns = await build_feature_matrix(
        async_db, start_date=_DATE, end_date=_DATE
    )

    assert rows[0]["alcohol_units"] is None


# ---------------------------------------------------------------------------
# had_alcohol derived column
# ---------------------------------------------------------------------------


async def test_had_alcohol_is_one_when_units_nonzero(
    async_db: AsyncSession,
) -> None:
    await _add_entry(async_db, _DATE, alcohol_units=3)
    rows, _ = await build_feature_matrix(
        async_db, start_date=_DATE, end_date=_DATE
    )

    assert rows[0]["had_alcohol"] == 1


async def test_had_alcohol_is_zero_when_units_zero(
    async_db: AsyncSession,
) -> None:
    await _add_entry(async_db, _DATE, alcohol_units=0)
    rows, _ = await build_feature_matrix(
        async_db, start_date=_DATE, end_date=_DATE
    )

    assert rows[0]["had_alcohol"] == 0


async def test_had_alcohol_is_zero_when_units_none(
    async_db: AsyncSession,
) -> None:
    await _add_entry(async_db, _DATE, alcohol_units=None)
    rows, _ = await build_feature_matrix(
        async_db, start_date=_DATE, end_date=_DATE
    )

    assert rows[0]["had_alcohol"] == 0


async def test_had_alcohol_is_none_when_no_entry(async_db: AsyncSession) -> None:
    # No entry for the date — row should have None (pre-fill default)
    rows, _ = await build_feature_matrix(
        async_db, start_date=_DATE, end_date=_DATE
    )

    assert rows[0]["had_alcohol"] is None


# ---------------------------------------------------------------------------
# caffeine_servings raw column
# ---------------------------------------------------------------------------


async def test_caffeine_servings_present_when_nonzero(
    async_db: AsyncSession,
) -> None:
    await _add_entry(async_db, _DATE, caffeine_servings=2)
    rows, columns = await build_feature_matrix(
        async_db, start_date=_DATE, end_date=_DATE
    )

    assert "caffeine_servings" in columns
    assert rows[0]["caffeine_servings"] == 2


async def test_caffeine_servings_zero(async_db: AsyncSession) -> None:
    await _add_entry(async_db, _DATE, caffeine_servings=0)
    rows, _ = await build_feature_matrix(
        async_db, start_date=_DATE, end_date=_DATE
    )

    assert rows[0]["caffeine_servings"] == 0


async def test_caffeine_servings_none(async_db: AsyncSession) -> None:
    await _add_entry(async_db, _DATE, caffeine_servings=None)
    rows, _ = await build_feature_matrix(
        async_db, start_date=_DATE, end_date=_DATE
    )

    assert rows[0]["caffeine_servings"] is None


# ---------------------------------------------------------------------------
# had_caffeine derived column
# ---------------------------------------------------------------------------


async def test_had_caffeine_is_one_when_servings_nonzero(
    async_db: AsyncSession,
) -> None:
    await _add_entry(async_db, _DATE, caffeine_servings=2)
    rows, _ = await build_feature_matrix(
        async_db, start_date=_DATE, end_date=_DATE
    )

    assert rows[0]["had_caffeine"] == 1


async def test_had_caffeine_is_zero_when_servings_zero(
    async_db: AsyncSession,
) -> None:
    await _add_entry(async_db, _DATE, caffeine_servings=0)
    rows, _ = await build_feature_matrix(
        async_db, start_date=_DATE, end_date=_DATE
    )

    assert rows[0]["had_caffeine"] == 0


async def test_had_caffeine_is_zero_when_servings_none(
    async_db: AsyncSession,
) -> None:
    await _add_entry(async_db, _DATE, caffeine_servings=None)
    rows, _ = await build_feature_matrix(
        async_db, start_date=_DATE, end_date=_DATE
    )

    assert rows[0]["had_caffeine"] == 0


async def test_had_caffeine_is_none_when_no_entry(async_db: AsyncSession) -> None:
    rows, _ = await build_feature_matrix(
        async_db, start_date=_DATE, end_date=_DATE
    )

    assert rows[0]["had_caffeine"] is None


# ---------------------------------------------------------------------------
# Column ordering
# ---------------------------------------------------------------------------


def test_new_columns_in_static_columns() -> None:
    assert "alcohol_units" in STATIC_COLUMNS
    assert "caffeine_servings" in STATIC_COLUMNS
    assert "had_alcohol" in STATIC_COLUMNS
    assert "had_caffeine" in STATIC_COLUMNS


def test_new_columns_after_hot_shower() -> None:
    hot_idx = STATIC_COLUMNS.index("hot_shower")
    assert STATIC_COLUMNS.index("alcohol_units") == hot_idx + 1
    assert STATIC_COLUMNS.index("caffeine_servings") == hot_idx + 2
    assert STATIC_COLUMNS.index("had_alcohol") == hot_idx + 3
    assert STATIC_COLUMNS.index("had_caffeine") == hot_idx + 4


def test_new_columns_before_stool_status() -> None:
    stool_idx = STATIC_COLUMNS.index("stool_status")
    for col in ("alcohol_units", "caffeine_servings", "had_alcohol", "had_caffeine"):
        assert STATIC_COLUMNS.index(col) < stool_idx


async def test_column_order_preserved_in_build_output(
    async_db: AsyncSession,
) -> None:
    await _add_entry(async_db, _DATE, alcohol_units=1, caffeine_servings=3)
    _, columns = await build_feature_matrix(
        async_db, start_date=_DATE, end_date=_DATE
    )

    hot_idx = columns.index("hot_shower")
    assert columns[hot_idx + 1] == "alcohol_units"
    assert columns[hot_idx + 2] == "caffeine_servings"
    assert columns[hot_idx + 3] == "had_alcohol"
    assert columns[hot_idx + 4] == "had_caffeine"


# ---------------------------------------------------------------------------
# CSV header coverage (columns list includes all four new cols)
# ---------------------------------------------------------------------------


async def test_csv_header_includes_all_four_new_columns(
    async_db: AsyncSession,
) -> None:
    await _add_entry(async_db, _DATE)
    _, columns = await build_feature_matrix(
        async_db, start_date=_DATE, end_date=_DATE
    )

    for col in ("alcohol_units", "caffeine_servings", "had_alcohol", "had_caffeine"):
        assert col in columns, f"{col!r} missing from columns"
