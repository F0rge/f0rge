from __future__ import annotations

import datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entry import Entry
from app.models.supplement_catalog import SupplementCatalogItem
from app.models.symptom_catalog import SymptomCatalogItem
from app.models.treatment import Treatment
from app.services.feature_matrix import STATIC_COLUMNS, build_feature_matrix
from app.services.signals.taxonomy import (
    MIRROR_COLUMNS_LAG0,
    TaxonomyError,
    resolve_class,
    resolve_shape,
)


async def _add_entry(db: AsyncSession, date: datetime.date) -> Entry:
    entry = Entry(
        date=date,
        schema_version=4,
        overall=3,
        bloating=1,
        joint_pain=0,
        neuro=3,
        sleep_quality=3,
        stress=1,
        diet_risk="normal",
        supplements="mag",
        sick=False,
        hot_shower=True,
        stool_status="normal",
        symptoms_json={"headache": 2},
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry


_NOW = datetime.datetime(2026, 1, 1, 12, 0, 0)


async def _add_supplement(db: AsyncSession, key: str) -> SupplementCatalogItem:
    item = SupplementCatalogItem(key=key, label=key.title(), sort_order=0)
    item.first_used_at = _NOW
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


async def _add_symptom(db: AsyncSession, key: str) -> SymptomCatalogItem:
    item = SymptomCatalogItem(key=key, label=key.title(), sort_order=0)
    item.first_used_at = _NOW
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


async def _add_treatment(db: AsyncSession, name: str, normalized: str) -> Treatment:
    t = Treatment(
        name=name,
        normalized_name=normalized,
        type="antimicrobial",
        start_date=datetime.date(2026, 5, 1),
    )
    db.add(t)
    await db.commit()
    await db.refresh(t)
    return t


_DATE = datetime.date(2026, 5, 15)


async def test_taxonomy_completeness_on_seeded_matrix(async_db: AsyncSession) -> None:
    await _add_supplement(async_db, "mag")
    await _add_symptom(async_db, "headache")
    await _add_treatment(async_db, "Allicin", "allicin")
    await _add_entry(async_db, _DATE)

    _, columns = await build_feature_matrix(async_db, _DATE, _DATE)

    for col in columns:
        feature_class = resolve_class(col, lag=0)
        assert feature_class in ("lever", "context", "mirror", "not-a-feature")
        if feature_class != "not-a-feature":
            shape = resolve_shape(col)
            assert shape in ("binary", "threshold", "linear", "interaction")

    for col in STATIC_COLUMNS:
        resolve_class(col, lag=0)


def test_mirror_columns_exhaustive_lag0() -> None:
    expected_mirrors = {
        "bloating",
        "joint_pain",
        "neuro",
        "stress",
        "sick",
        "stool_status",
        "bristol_type",
        "sleep_quality",
        "photo_count",
        "ingredient_count",
        "hm_hrv_mean",
        "hm_hrv_std",
        "hm_resting_hr",
        "hm_spo2",
        "hm_wrist_temp_deviation",
        "hm_steps",
        "hm_active_minutes",
    }
    assert expected_mirrors <= MIRROR_COLUMNS_LAG0
    for col in expected_mirrors:
        assert resolve_class(col, lag=0) == "mirror"


def test_physiology_context_at_lag1() -> None:
    for col in (
        "hm_hrv_mean",
        "hm_resting_hr",
        "hm_spo2",
        "hm_wrist_temp_deviation",
    ):
        assert resolve_class(col, lag=0) == "mirror"
        assert resolve_class(col, lag=1) == "context"


def test_activity_lever_at_lag1_only() -> None:
    assert resolve_class("hm_steps", lag=0) == "mirror"
    assert resolve_class("hm_steps", lag=1) == "lever"
    assert resolve_class("hm_active_minutes", lag=1) == "lever"


def test_dynamic_prefix_rules() -> None:
    assert resolve_class("sym_headache", lag=0) == "mirror"
    assert resolve_class("supp_mag", lag=0) == "lever"
    assert resolve_class("tx_allicin_active", lag=0) == "lever"
    assert resolve_shape("supp_mag") == "binary"
    assert resolve_shape("sym_headache") == "linear"


def test_unknown_column_raises() -> None:
    with pytest.raises(TaxonomyError):
        resolve_class("not_a_real_column_xyz")
    with pytest.raises(TaxonomyError):
        resolve_shape("not_a_real_column_xyz")
