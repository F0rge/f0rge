from __future__ import annotations

import datetime

import pytest
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entry import Entry
from app.models.symptom_catalog import SymptomCatalogItem
from app.schemas.entry import EntryCreate, EntryResponse
from app.services import entries as entries_service
from app.services import symptom_catalog as symptom_catalog_service


async def _make_entry(
    db: AsyncSession,
    date: datetime.date,
    symptoms_json: dict | None = None,
) -> Entry:
    """Helper: create an Entry directly via ORM (bypasses router)."""
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


_DATE = datetime.date(2026, 5, 15)


# ---------------------------------------------------------------------------
# Schema validation — Pydantic layer
# ---------------------------------------------------------------------------


def test_schema_valid_symptoms_json() -> None:
    data = EntryCreate(
        date=_DATE,
        overall=2,
        bloating=0,
        joint_pain=0,
        neuro=0,
        sleep_quality=2,
        stress=1,
        diet_risk="normal",
        supplements="",
        sick=False,
        symptoms_json={"vss": 7, "tinnitus": 6},
    )
    assert data.symptoms_json == {"vss": 7, "tinnitus": 6}


def test_schema_severity_out_of_range_raises() -> None:
    with pytest.raises(PydanticValidationError, match="severity must be integer 0-10"):
        EntryCreate(
            date=_DATE,
            overall=2,
            bloating=0,
            joint_pain=0,
            neuro=0,
            sleep_quality=2,
            stress=1,
            diet_risk="normal",
            supplements="",
            sick=False,
            symptoms_json={"vss": 11},
        )


def test_schema_uppercase_key_raises() -> None:
    with pytest.raises(PydanticValidationError, match=r"\^.a-z0-9_"):
        EntryCreate(
            date=_DATE,
            overall=2,
            bloating=0,
            joint_pain=0,
            neuro=0,
            sleep_quality=2,
            stress=1,
            diet_risk="normal",
            supplements="",
            sick=False,
            symptoms_json={"VSS": 7},
        )


def test_schema_non_int_value_raises() -> None:
    with pytest.raises(PydanticValidationError, match="severity must be integer 0-10"):
        EntryCreate(
            date=_DATE,
            overall=2,
            bloating=0,
            joint_pain=0,
            neuro=0,
            sleep_quality=2,
            stress=1,
            diet_risk="normal",
            supplements="",
            sick=False,
            symptoms_json={"vss": "high"},  # type: ignore[dict-item]
        )


def test_schema_omitted_symptoms_json_defaults_to_none() -> None:
    data = EntryCreate(
        date=_DATE,
        overall=2,
        bloating=0,
        joint_pain=0,
        neuro=0,
        sleep_quality=2,
        stress=1,
        diet_risk="normal",
        supplements="",
        sick=False,
    )
    assert data.symptoms_json is None


# ---------------------------------------------------------------------------
# ORM / service layer
# ---------------------------------------------------------------------------


async def test_entry_stores_and_retrieves_symptoms_json(async_db: AsyncSession) -> None:
    await _make_entry(async_db, _DATE, {"vss": 7, "tinnitus": 6})
    # Re-fetch from DB to verify persistence
    fetched = (
        await async_db.execute(select(Entry).where(Entry.date == _DATE))
    ).scalar_one()
    assert fetched.symptoms_json == {"vss": 7, "tinnitus": 6}


async def test_entry_omitted_symptoms_defaults_to_empty_dict(
    async_db: AsyncSession,
) -> None:
    entry = await _make_entry(async_db, _DATE)
    assert entry.symptoms_json == {}

    response = entries_service._build_response(entry)
    assert response.symptoms_json == {}


async def test_touch_sets_catalog_timestamps_after_create(
    async_db: AsyncSession,
) -> None:
    """After creating an entry that references 'vss', the catalog row should
    have first_used_at and last_used_at populated."""
    await symptom_catalog_service.create_item(async_db, "vss", "Visual Snow")

    entry = await _make_entry(async_db, _DATE, {"vss": 7})
    # Simulate what the router does after add/before commit
    await symptom_catalog_service.touch(async_db, list(entry.symptoms_json.keys()))
    await async_db.commit()

    item = (
        await async_db.execute(
            select(SymptomCatalogItem).where(SymptomCatalogItem.key == "vss")
        )
    ).scalar_one()
    assert item.first_used_at is not None
    assert item.last_used_at is not None


async def test_touch_on_update_sets_first_used_at_for_new_symptom(
    async_db: AsyncSession,
) -> None:
    """Adding a new symptom during an update should set first_used_at."""
    await symptom_catalog_service.create_item(async_db, "tinnitus", "Tinnitus")
    entry = await _make_entry(async_db, _DATE, {})

    # Simulate update adding tinnitus
    entry.symptoms_json = {"tinnitus": 5}
    async_db.add(entry)
    await symptom_catalog_service.touch(async_db, list(entry.symptoms_json.keys()))
    await async_db.commit()
    await async_db.refresh(entry)

    item = (
        await async_db.execute(
            select(SymptomCatalogItem).where(SymptomCatalogItem.key == "tinnitus")
        )
    ).scalar_one()
    assert item.first_used_at is not None


async def test_touch_silently_ignores_unknown_keys(async_db: AsyncSession) -> None:
    """touch() must not raise when a key is not in the catalog."""
    entry = await _make_entry(async_db, _DATE, {"unknown_xyz": 5})
    # Should not raise
    await symptom_catalog_service.touch(async_db, list(entry.symptoms_json.keys()))
    await async_db.commit()
