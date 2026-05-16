from __future__ import annotations

import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entry import Entry
from app.models.symptom_catalog import SymptomCatalogItem
from app.services.feature_matrix import (
    FEATURE_SCHEMA_VERSION,
    STATIC_COLUMNS,
    _DIET_RISK_ORDINAL,
    build_feature_matrix,
)


async def _add_entry(
    db: AsyncSession,
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
    await db.commit()
    await db.refresh(entry)
    return entry


async def _add_sym_item(
    db: AsyncSession,
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
    await db.commit()
    await db.refresh(item)
    return item


_DATE = datetime.date(2026, 5, 15)
_NOW = datetime.datetime(2026, 5, 15, 12, 0, 0)


# ---------------------------------------------------------------------------
# No entries → no sym_* columns
# ---------------------------------------------------------------------------


async def test_no_entries_no_sym_columns(async_db: AsyncSession) -> None:
    rows, columns = await build_feature_matrix(async_db, _DATE, _DATE)
    sym_cols = [c for c in columns if c.startswith("sym_")]
    assert sym_cols == []


# ---------------------------------------------------------------------------
# Entry with vss → sym_vss column appears with correct value
# ---------------------------------------------------------------------------


async def test_entry_with_symptom_creates_column(async_db: AsyncSession) -> None:
    await _add_sym_item(async_db, "vss", "Visual Snow", first_used_at=_NOW)
    await _add_entry(async_db, _DATE, {"vss": 7})

    rows, columns = await build_feature_matrix(async_db, _DATE, _DATE)
    assert "sym_vss" in columns
    assert rows[0]["sym_vss"] == 7


# ---------------------------------------------------------------------------
# Other dates get None for sym_* value
# ---------------------------------------------------------------------------


async def test_other_dates_get_none_for_symptom(async_db: AsyncSession) -> None:
    await _add_sym_item(async_db, "vss", "Visual Snow", first_used_at=_NOW)
    await _add_entry(async_db, _DATE, {"vss": 7})
    other_date = _DATE - datetime.timedelta(days=1)
    await _add_entry(async_db, other_date, {})

    rows, columns = await build_feature_matrix(async_db, other_date, _DATE)
    by_date = {r["date"]: r for r in rows}
    assert by_date[other_date.isoformat()]["sym_vss"] is None
    assert by_date[_DATE.isoformat()]["sym_vss"] == 7


# ---------------------------------------------------------------------------
# Archived symptom is excluded even with historical first_used_at
# ---------------------------------------------------------------------------


async def test_archived_symptom_excluded_from_columns(
    async_db: AsyncSession,
) -> None:
    await _add_sym_item(
        async_db, "vss", "Visual Snow", archived=True, first_used_at=_NOW
    )
    await _add_entry(async_db, _DATE, {"vss": 7})

    rows, columns = await build_feature_matrix(async_db, _DATE, _DATE)
    sym_cols = [c for c in columns if c.startswith("sym_")]
    assert sym_cols == []


# ---------------------------------------------------------------------------
# Column ordering: STATIC + supp_* + tx_* + sym_*
# ---------------------------------------------------------------------------


async def test_column_order_static_then_supp_then_tx_then_sym(
    async_db: AsyncSession,
) -> None:
    await _add_sym_item(async_db, "tinnitus", "Tinnitus", first_used_at=_NOW)
    await _add_entry(async_db, _DATE, {"tinnitus": 5})

    rows, columns = await build_feature_matrix(async_db, _DATE, _DATE)

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


# ---------------------------------------------------------------------------
# diet_risk ordinal encoding
# ---------------------------------------------------------------------------


async def _add_entry_with_diet_risk(
    db: AsyncSession,
    date: datetime.date,
    diet_risk: str | None,
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
        diet_risk=diet_risk,
        supplements="",
        sick=False,
        hot_shower=False,
        symptoms_json={},
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry


async def test_diet_risk_low_encodes_as_1(async_db: AsyncSession) -> None:
    await _add_entry_with_diet_risk(async_db, _DATE, "low")
    rows, _ = await build_feature_matrix(async_db, _DATE, _DATE)
    assert rows[0]["diet_risk"] == 1


async def test_diet_risk_high_encodes_as_3(async_db: AsyncSession) -> None:
    await _add_entry_with_diet_risk(async_db, _DATE, "high")
    rows, _ = await build_feature_matrix(async_db, _DATE, _DATE)
    assert rows[0]["diet_risk"] == 3


def test_diet_risk_none_encodes_as_none() -> None:
    # diet_risk=None cannot be persisted (NOT NULL column); test the mapping directly.
    assert _DIET_RISK_ORDINAL.get(None) is None


async def test_diet_risk_minimal_encodes_as_0(async_db: AsyncSession) -> None:
    await _add_entry_with_diet_risk(async_db, _DATE, "minimal")
    rows, _ = await build_feature_matrix(async_db, _DATE, _DATE)
    assert rows[0]["diet_risk"] == 0


async def test_diet_risk_normal_encodes_as_2(async_db: AsyncSession) -> None:
    await _add_entry_with_diet_risk(async_db, _DATE, "normal")
    rows, _ = await build_feature_matrix(async_db, _DATE, _DATE)
    assert rows[0]["diet_risk"] == 2


def test_feature_schema_version_is_3() -> None:
    """Ordinal diet_risk encoding bumped the schema version to 3."""
    assert FEATURE_SCHEMA_VERSION == 3
