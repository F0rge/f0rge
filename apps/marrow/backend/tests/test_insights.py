from __future__ import annotations

import datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from f0rge_core.exceptions import ValidationError
from app.models.entry import Entry
from app.models.symptom_catalog import SymptomCatalogItem
from app.models.treatment import Treatment
from app.services.insights import InsightsService


_BASE_DATE = datetime.date(2026, 1, 1)
_NOW = datetime.datetime(2026, 1, 1, 12, 0, 0)


async def _add_entry(
    db: AsyncSession,
    date: datetime.date,
    overall: int = 3,
    bloating: int = 1,
    joint_pain: int = 0,
    neuro: int = 0,
    sleep_quality: int = 2,
    stress: int = 1,
    diet_risk: str = "normal",
    sick: bool = False,
    symptoms_json: dict | None = None,
    supplements: str = "",
) -> Entry:
    entry = Entry(
        date=date,
        schema_version=3,
        overall=overall,
        bloating=bloating,
        stool_status="normal",
        joint_pain=joint_pain,
        neuro=neuro,
        sleep_quality=sleep_quality,
        stress=stress,
        diet_risk=diet_risk,
        sick=sick,
        hot_shower=False,
        supplements=supplements,
        symptoms_json=symptoms_json or {},
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry


async def _add_sym_item(
    db: AsyncSession,
    key: str,
    label: str,
) -> SymptomCatalogItem:
    item = SymptomCatalogItem(
        key=key,
        label=label,
        archived=False,
        sort_order=0,
        first_used_at=_NOW,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


async def _add_treatment(
    db: AsyncSession,
    name: str,
    tx_type: str,
    start_date: datetime.date,
    end_date: datetime.date | None = None,
    normalized_name: str | None = None,
) -> Treatment:
    tx = Treatment(
        name=name,
        normalized_name=normalized_name or name.lower().replace(" ", "_"),
        type=tx_type,
        start_date=start_date,
        end_date=end_date,
    )
    db.add(tx)
    await db.commit()
    await db.refresh(tx)
    return tx


# ── compute_trends ────────────────────────────────────────────────────────────


async def test_trends_returns_series_for_core_keys(async_db: AsyncSession) -> None:
    for i in range(10):
        await _add_entry(async_db, _BASE_DATE + datetime.timedelta(days=i), overall=i % 5)
    result = await InsightsService(async_db).compute_trends(
        _BASE_DATE, _BASE_DATE + datetime.timedelta(days=9)
    )
    keys = {s.key for s in result.series}
    assert "overall" in keys
    assert "bloating" in keys


async def test_trends_includes_sym_columns(async_db: AsyncSession) -> None:
    await _add_sym_item(async_db, "vss", "Visual Snow")
    for i in range(5):
        await _add_entry(
            async_db,
            _BASE_DATE + datetime.timedelta(days=i),
            symptoms_json={"vss": i + 1},
        )
    result = await InsightsService(async_db).compute_trends(
        _BASE_DATE, _BASE_DATE + datetime.timedelta(days=4)
    )
    keys = {s.key for s in result.series}
    assert "sym_vss" in keys


async def test_trends_rolling_avg_7_computed(async_db: AsyncSession) -> None:
    # Seed 10 days with overall = day index (0-9)
    for i in range(10):
        await _add_entry(async_db, _BASE_DATE + datetime.timedelta(days=i), overall=i)
    result = await InsightsService(async_db).compute_trends(
        _BASE_DATE, _BASE_DATE + datetime.timedelta(days=9)
    )
    overall_series = next(s for s in result.series if s.key == "overall")
    # points[6].rolling_avg_7 = mean(0,1,2,3,4,5,6)
    assert overall_series.points[6].rolling_avg_7 == pytest.approx(3.0, abs=0.01)


async def test_trends_delta_30d_computed(async_db: AsyncSession) -> None:
    for i in range(35):
        await _add_entry(async_db, _BASE_DATE + datetime.timedelta(days=i), overall=i % 5)
    result = await InsightsService(async_db).compute_trends(
        _BASE_DATE, _BASE_DATE + datetime.timedelta(days=34)
    )
    overall_series = next(s for s in result.series if s.key == "overall")
    # delta_30d should be set (not None) when we have >= 30 points
    assert overall_series.delta_30d is not None


# ── compute_treatment_response ────────────────────────────────────────────────


async def test_treatment_response_invalid_outcome_raises(
    async_db: AsyncSession,
) -> None:
    with pytest.raises(ValidationError):
        await InsightsService(async_db).compute_treatment_response("not_real")


async def test_treatment_response_windows_correct(async_db: AsyncSession) -> None:
    """Baseline, during, and after windows segment without overlap."""
    tx_start = _BASE_DATE + datetime.timedelta(days=35)
    tx_end = tx_start + datetime.timedelta(days=14)
    await _add_treatment(async_db, "Probiotic", "supplement", tx_start, tx_end)

    # Seed baseline: 30 days before start
    for i in range(30):
        d = tx_start - datetime.timedelta(days=30 - i)
        await _add_entry(async_db, d, overall=2)

    # During window: 15 days
    for i in range(15):
        d = tx_start + datetime.timedelta(days=i)
        await _add_entry(async_db, d, overall=4)

    # After window: 20 days after end
    for i in range(20):
        d = tx_end + datetime.timedelta(days=i + 1)
        await _add_entry(async_db, d, overall=3)

    result = await InsightsService(async_db).compute_treatment_response("overall")
    assert len(result.rows) == 1
    row = result.rows[0]

    assert row.baseline_mean == pytest.approx(2.0, abs=0.01)
    assert row.during_mean == pytest.approx(4.0, abs=0.01)
    assert row.after_mean == pytest.approx(3.0, abs=0.01)
    assert row.delta_during_vs_baseline == pytest.approx(2.0, abs=0.01)
    assert row.baseline_n == 30
    assert row.during_n == 15
    assert row.after_n >= 20  # At least 20 days after end


async def test_treatment_response_skips_insufficient_baseline(
    async_db: AsyncSession,
) -> None:
    """Treatment with < 5 baseline data points must be excluded from results."""
    tx_start = _BASE_DATE + datetime.timedelta(days=3)
    await _add_treatment(async_db, "Short", "diet", tx_start)

    # Only 3 baseline entries (< 5 required)
    for i in range(3):
        d = tx_start - datetime.timedelta(days=3 - i)
        await _add_entry(async_db, d, overall=2)

    result = await InsightsService(async_db).compute_treatment_response("overall")
    assert len(result.rows) == 0


async def test_treatment_response_no_after_window_when_ongoing(
    async_db: AsyncSession,
) -> None:
    """Ongoing treatment (no end_date) should have after_mean=None, after_n=0."""
    tx_start = _BASE_DATE + datetime.timedelta(days=35)
    await _add_treatment(async_db, "Ongoing Tx", "medication", tx_start, end_date=None)

    for i in range(30):
        d = tx_start - datetime.timedelta(days=30 - i)
        await _add_entry(async_db, d, overall=2)

    for i in range(10):
        d = tx_start + datetime.timedelta(days=i)
        await _add_entry(async_db, d, overall=4)

    result = await InsightsService(async_db).compute_treatment_response("overall")
    assert len(result.rows) == 1
    row = result.rows[0]
    assert row.end_date is None
    assert row.after_mean is None
    assert row.after_n == 0
