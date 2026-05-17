from __future__ import annotations

import datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ValidationError
from app.models.entry import Entry
from app.models.health_metrics import HealthMetric
from app.models.symptom_catalog import SymptomCatalogItem
from app.models.treatment import Treatment
from app.services.insights import (
    compute_correlates,
    compute_sleep_next_day,
    compute_treatment_response,
    compute_trends,
)


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


async def _add_hm(
    db: AsyncSession,
    date: datetime.date,
    hrv_mean: float | None = None,
    resting_hr: float | None = None,
    sleep_efficiency: float | None = None,
    sleep_rem_min: float | None = None,
    sleep_deep_min: float | None = None,
) -> HealthMetric:
    hm = HealthMetric(
        date=date,
        hrv_mean=hrv_mean,
        resting_hr=resting_hr,
        sleep_efficiency=sleep_efficiency,
        sleep_rem_min=sleep_rem_min,
        sleep_deep_min=sleep_deep_min,
    )
    db.add(hm)
    await db.commit()
    await db.refresh(hm)
    return hm


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
        await _add_entry(
            async_db, _BASE_DATE + datetime.timedelta(days=i), overall=i % 5
        )
    result = await compute_trends(
        async_db, _BASE_DATE, _BASE_DATE + datetime.timedelta(days=9)
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
    result = await compute_trends(
        async_db, _BASE_DATE, _BASE_DATE + datetime.timedelta(days=4)
    )
    keys = {s.key for s in result.series}
    assert "sym_vss" in keys


async def test_trends_rolling_avg_7_computed(async_db: AsyncSession) -> None:
    # Seed 10 days with overall = day index (0-9)
    for i in range(10):
        await _add_entry(async_db, _BASE_DATE + datetime.timedelta(days=i), overall=i)
    result = await compute_trends(
        async_db, _BASE_DATE, _BASE_DATE + datetime.timedelta(days=9)
    )
    overall_series = next(s for s in result.series if s.key == "overall")
    # points[6].rolling_avg_7 = mean(0,1,2,3,4,5,6)
    assert overall_series.points[6].rolling_avg_7 == pytest.approx(3.0, abs=0.01)


async def test_trends_delta_30d_computed(async_db: AsyncSession) -> None:
    for i in range(35):
        await _add_entry(
            async_db, _BASE_DATE + datetime.timedelta(days=i), overall=i % 5
        )
    result = await compute_trends(
        async_db, _BASE_DATE, _BASE_DATE + datetime.timedelta(days=34)
    )
    overall_series = next(s for s in result.series if s.key == "overall")
    # delta_30d should be set (not None) when we have >= 30 points
    assert overall_series.delta_30d is not None


# ── compute_correlates ────────────────────────────────────────────────────────


async def test_correlates_invalid_outcome_raises(async_db: AsyncSession) -> None:
    with pytest.raises(ValidationError):
        await compute_correlates(async_db, None, None, "not_a_real_outcome", None, 3)


async def test_correlates_hrv_correlates_with_overall(
    async_db: AsyncSession,
) -> None:
    """HRV mean seeded to inversely track overall — higher HRV → lower overall."""
    n_days = 20
    for i in range(n_days):
        overall_val = (i % 5) + 1
        hrv_val = float(6 - overall_val) * 10  # inverse: overall=1 → hrv=50
        await _add_entry(
            async_db,
            _BASE_DATE + datetime.timedelta(days=i),
            overall=overall_val,
        )
        await _add_hm(
            async_db,
            _BASE_DATE + datetime.timedelta(days=i),
            hrv_mean=hrv_val,
        )

    result = await compute_correlates(
        async_db,
        _BASE_DATE,
        _BASE_DATE + datetime.timedelta(days=n_days - 1),
        "overall",
        None,
        min_n=5,
    )
    features = {r.feature: r for r in result.negative}
    assert "hm_hrv_mean" in features
    assert features["hm_hrv_mean"].rho < -0.5


async def test_correlates_lag_selection(async_db: AsyncSession) -> None:
    """Feature at t-2 should be picked as best_lag=2 when it's the strongest signal."""
    n_days = 30
    signal = [float((i % 7) + 1) for i in range(n_days + 2)]

    for i in range(n_days + 2):
        d = _BASE_DATE + datetime.timedelta(days=i)
        overall_val = int(signal[i - 2]) if i >= 2 else 3
        await _add_entry(async_db, d, overall=overall_val)
        await _add_hm(async_db, d, hrv_mean=signal[i])

    result = await compute_correlates(
        async_db,
        _BASE_DATE,
        _BASE_DATE + datetime.timedelta(days=n_days + 1),
        "overall",
        "metric",
        min_n=5,
    )

    hrv_rows = [
        r for r in result.positive + result.negative if r.feature == "hm_hrv_mean"
    ]
    if hrv_rows:
        assert hrv_rows[0].best_lag == 2


async def test_correlates_category_filter(async_db: AsyncSession) -> None:
    """category filter should restrict results to that category."""
    for i in range(20):
        await _add_entry(
            async_db, _BASE_DATE + datetime.timedelta(days=i), overall=i % 5
        )
        await _add_hm(
            async_db, _BASE_DATE + datetime.timedelta(days=i), hrv_mean=float(i)
        )

    result = await compute_correlates(
        async_db,
        _BASE_DATE,
        _BASE_DATE + datetime.timedelta(days=19),
        "overall",
        "sleep",  # only sleep category
        min_n=5,
    )
    for row in result.positive + result.negative:
        assert row.category == "sleep"


async def test_correlates_sym_outcome_allowed(async_db: AsyncSession) -> None:
    await _add_sym_item(async_db, "brain_fog", "Brain Fog")
    for i in range(20):
        await _add_entry(
            async_db,
            _BASE_DATE + datetime.timedelta(days=i),
            symptoms_json={"brain_fog": i % 5},
        )
    # Should not raise — sym_ outcomes are in the whitelist
    result = await compute_correlates(
        async_db, None, None, "sym_brain_fog", None, min_n=3
    )
    assert result.outcome == "sym_brain_fog"


# ── compute_treatment_response ────────────────────────────────────────────────


async def test_treatment_response_invalid_outcome_raises(
    async_db: AsyncSession,
) -> None:
    with pytest.raises(ValidationError):
        await compute_treatment_response(async_db, "not_real")


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

    result = await compute_treatment_response(async_db, "overall")
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

    result = await compute_treatment_response(async_db, "overall")
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

    result = await compute_treatment_response(async_db, "overall")
    assert len(result.rows) == 1
    row = result.rows[0]
    assert row.end_date is None
    assert row.after_mean is None
    assert row.after_n == 0


# ── compute_sleep_next_day ────────────────────────────────────────────────────


async def test_sleep_next_day_invalid_outcome_raises(
    async_db: AsyncSession,
) -> None:
    with pytest.raises(ValidationError):
        await compute_sleep_next_day(
            async_db, None, None, "not_real", "hm_sleep_rem_min"
        )


async def test_sleep_next_day_invalid_metric_raises(
    async_db: AsyncSession,
) -> None:
    for i in range(5):
        await _add_entry(async_db, _BASE_DATE + datetime.timedelta(days=i), overall=i)
    with pytest.raises(ValidationError):
        await compute_sleep_next_day(
            async_db, None, None, "overall", "hm_invalid_metric"
        )


async def test_sleep_next_day_pairs_correctly(async_db: AsyncSession) -> None:
    """Each point pairs sleep[i] with outcome[i+1]. Last sleep row has no pair."""
    n_days = 10
    for i in range(n_days):
        d = _BASE_DATE + datetime.timedelta(days=i)
        await _add_entry(async_db, d, overall=i + 1)
        await _add_hm(async_db, d, sleep_rem_min=float(60 + i * 2))

    result = await compute_sleep_next_day(
        async_db,
        _BASE_DATE,
        _BASE_DATE + datetime.timedelta(days=n_days - 1),
        "overall",
        "hm_sleep_rem_min",
    )
    assert len(result.points) == n_days - 1

    # First point: sleep on day 0, outcome on day 1
    first = result.points[0]
    assert first.sleep_value == pytest.approx(60.0)
    assert first.next_day_outcome == pytest.approx(2.0)  # overall on day 1


async def test_sleep_next_day_orphaned_last_day_dropped(
    async_db: AsyncSession,
) -> None:
    """When the last sleep metric has no following entry, the pair is dropped."""
    for i in range(5):
        d = _BASE_DATE + datetime.timedelta(days=i)
        await _add_entry(async_db, d, overall=i + 1)
        await _add_hm(async_db, d, sleep_rem_min=60.0)
    # Add a health metric on day 5 with NO corresponding entry
    await _add_hm(async_db, _BASE_DATE + datetime.timedelta(days=5), sleep_rem_min=70.0)

    result = await compute_sleep_next_day(
        async_db,
        _BASE_DATE,
        _BASE_DATE + datetime.timedelta(days=5),
        "overall",
        "hm_sleep_rem_min",
    )
    for pt in result.points:
        assert pt.next_day_outcome is not None
        assert pt.sleep_value is not None


async def test_correlates_sick_is_valid_outcome(
    async_db: AsyncSession,
) -> None:
    """sick is a core outcome; compute_correlates must accept it without raising."""
    for i in range(15):
        d = _BASE_DATE + datetime.timedelta(days=i)
        await _add_entry(async_db, d)

    # Must not raise ValidationError
    result = await compute_correlates(async_db, None, None, "sick", None, min_n=3)
    assert result.outcome == "sick"


async def test_sleep_next_day_rho_returned(async_db: AsyncSession) -> None:
    # Strong synthetic correlation
    for i in range(15):
        d = _BASE_DATE + datetime.timedelta(days=i)
        await _add_entry(async_db, d, overall=i + 1)
        await _add_hm(async_db, d, sleep_efficiency=float(50 + i * 2))

    result = await compute_sleep_next_day(
        async_db,
        _BASE_DATE,
        _BASE_DATE + datetime.timedelta(days=14),
        "overall",
        "hm_sleep_efficiency",
    )
    assert result.rho is not None
    assert result.n >= 5
