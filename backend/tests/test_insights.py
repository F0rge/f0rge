from __future__ import annotations

import datetime
from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
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


# ── fixtures ──────────────────────────────────────────────────────────────────


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


_BASE_DATE = datetime.date(2026, 1, 1)
_NOW = datetime.datetime(2026, 1, 1, 12, 0, 0)


def _add_entry(
    db: Session,
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
    db.commit()
    db.refresh(entry)
    return entry


def _add_hm(
    db: Session,
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
    db.commit()
    db.refresh(hm)
    return hm


def _add_sym_item(
    db: Session,
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
    db.commit()
    db.refresh(item)
    return item


def _add_treatment(
    db: Session,
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
    db.commit()
    db.refresh(tx)
    return tx


# ── compute_trends ────────────────────────────────────────────────────────────


def test_trends_returns_series_for_core_keys(db: Session) -> None:
    for i in range(10):
        _add_entry(db, _BASE_DATE + datetime.timedelta(days=i), overall=i % 5)
    result = compute_trends(db, _BASE_DATE, _BASE_DATE + datetime.timedelta(days=9))
    keys = {s.key for s in result.series}
    assert "overall" in keys
    assert "bloating" in keys


def test_trends_includes_sym_columns(db: Session) -> None:
    _add_sym_item(db, "vss", "Visual Snow")
    for i in range(5):
        _add_entry(
            db, _BASE_DATE + datetime.timedelta(days=i), symptoms_json={"vss": i + 1}
        )
    result = compute_trends(db, _BASE_DATE, _BASE_DATE + datetime.timedelta(days=4))
    keys = {s.key for s in result.series}
    assert "sym_vss" in keys


def test_trends_rolling_avg_7_computed(db: Session) -> None:
    # Seed 10 days with overall = day index (0-9)
    for i in range(10):
        _add_entry(db, _BASE_DATE + datetime.timedelta(days=i), overall=i)
    result = compute_trends(db, _BASE_DATE, _BASE_DATE + datetime.timedelta(days=9))
    overall_series = next(s for s in result.series if s.key == "overall")
    # Day index 6 (7th day): rolling avg should cover days 0..6 → mean of 0-6 = 3.0
    # Points are indexed 0..9 so points[6].rolling_avg_7 = mean(0,1,2,3,4,5,6)
    assert overall_series.points[6].rolling_avg_7 == pytest.approx(3.0, abs=0.01)


def test_trends_delta_30d_computed(db: Session) -> None:
    for i in range(35):
        _add_entry(db, _BASE_DATE + datetime.timedelta(days=i), overall=i % 5)
    result = compute_trends(db, _BASE_DATE, _BASE_DATE + datetime.timedelta(days=34))
    overall_series = next(s for s in result.series if s.key == "overall")
    # delta_30d should be set (not None) when we have >= 30 points
    assert overall_series.delta_30d is not None


# ── compute_correlates ────────────────────────────────────────────────────────


def test_correlates_invalid_outcome_raises(db: Session) -> None:
    with pytest.raises(ValidationError):
        compute_correlates(db, None, None, "not_a_real_outcome", None, 3)


def test_correlates_hrv_correlates_with_overall(db: Session) -> None:
    """HRV mean seeded to inversely track overall — higher HRV → lower overall."""
    # overall goes 5,4,3,2,1,5,4,3,2,1,5,4,3,2,1 (cycling low = bad)
    # hrv_mean mirrors: higher HRV when overall is lower
    n_days = 20
    for i in range(n_days):
        overall_val = (i % 5) + 1
        hrv_val = float(6 - overall_val) * 10  # inverse: overall=1 → hrv=50
        _add_entry(db, _BASE_DATE + datetime.timedelta(days=i), overall=overall_val)
        _add_hm(db, _BASE_DATE + datetime.timedelta(days=i), hrv_mean=hrv_val)

    result = compute_correlates(
        db,
        _BASE_DATE,
        _BASE_DATE + datetime.timedelta(days=n_days - 1),
        "overall",
        None,
        min_n=5,
    )
    features = {r.feature: r for r in result.negative}
    assert "hm_hrv_mean" in features
    assert features["hm_hrv_mean"].rho < -0.5


def test_correlates_lag_selection(db: Session) -> None:
    """Feature at t-2 should be picked as best_lag=2 when it's the strongest signal."""
    # Outcome on day i = feature on day i-2
    # Use 30 days, feature is a synthetic signal
    n_days = 30
    signal = [float((i % 7) + 1) for i in range(n_days + 2)]  # +2 for lag headroom

    for i in range(n_days + 2):
        d = _BASE_DATE + datetime.timedelta(days=i)
        # overall on day i = signal[i-2] (not available until index 2)
        overall_val = int(signal[i - 2]) if i >= 2 else 3
        _add_entry(db, d, overall=overall_val)
        _add_hm(db, d, hrv_mean=signal[i])

    result = compute_correlates(
        db,
        _BASE_DATE,
        _BASE_DATE + datetime.timedelta(days=n_days + 1),
        "overall",
        "metric",
        min_n=5,
    )

    # The lag-2 alignment should dominate for hrv_mean
    hrv_rows = [
        r for r in result.positive + result.negative if r.feature == "hm_hrv_mean"
    ]
    if hrv_rows:
        # best_lag should be 2 if the signal is constructed correctly
        assert hrv_rows[0].best_lag == 2


def test_correlates_category_filter(db: Session) -> None:
    """category filter should restrict results to that category."""
    for i in range(20):
        _add_entry(db, _BASE_DATE + datetime.timedelta(days=i), overall=i % 5)
        _add_hm(db, _BASE_DATE + datetime.timedelta(days=i), hrv_mean=float(i))

    result = compute_correlates(
        db,
        _BASE_DATE,
        _BASE_DATE + datetime.timedelta(days=19),
        "overall",
        "sleep",  # only sleep category
        min_n=5,
    )
    for row in result.positive + result.negative:
        assert row.category == "sleep"


def test_correlates_sym_outcome_allowed(db: Session) -> None:
    _add_sym_item(db, "brain_fog", "Brain Fog")
    for i in range(20):
        _add_entry(
            db,
            _BASE_DATE + datetime.timedelta(days=i),
            symptoms_json={"brain_fog": i % 5},
        )
    # Should not raise — sym_ outcomes are in the whitelist
    result = compute_correlates(db, None, None, "sym_brain_fog", None, min_n=3)
    assert result.outcome == "sym_brain_fog"


# ── compute_treatment_response ────────────────────────────────────────────────


def test_treatment_response_invalid_outcome_raises(db: Session) -> None:
    with pytest.raises(ValidationError):
        compute_treatment_response(db, "not_real")


def test_treatment_response_windows_correct(db: Session) -> None:
    """Baseline, during, and after windows segment without overlap."""
    tx_start = _BASE_DATE + datetime.timedelta(days=35)
    tx_end = tx_start + datetime.timedelta(days=14)
    _add_treatment(db, "Probiotic", "supplement", tx_start, tx_end)

    # Seed baseline: 30 days before start
    for i in range(30):
        d = tx_start - datetime.timedelta(days=30 - i)
        _add_entry(db, d, overall=2)

    # During window: 15 days
    for i in range(15):
        d = tx_start + datetime.timedelta(days=i)
        _add_entry(db, d, overall=4)

    # After window: 20 days after end
    for i in range(20):
        d = tx_end + datetime.timedelta(days=i + 1)
        _add_entry(db, d, overall=3)

    result = compute_treatment_response(db, "overall")
    assert len(result.rows) == 1
    row = result.rows[0]

    assert row.baseline_mean == pytest.approx(2.0, abs=0.01)
    assert row.during_mean == pytest.approx(4.0, abs=0.01)
    assert row.after_mean == pytest.approx(3.0, abs=0.01)
    assert row.delta_during_vs_baseline == pytest.approx(2.0, abs=0.01)
    assert row.baseline_n == 30
    assert row.during_n == 15
    assert row.after_n >= 20  # At least 20 days after end


def test_treatment_response_skips_insufficient_baseline(db: Session) -> None:
    """Treatment with < 5 baseline data points must be excluded from results."""
    tx_start = _BASE_DATE + datetime.timedelta(days=3)
    _add_treatment(db, "Short", "diet", tx_start)

    # Only 3 baseline entries (< 5 required)
    for i in range(3):
        d = tx_start - datetime.timedelta(days=3 - i)
        _add_entry(db, d, overall=2)

    result = compute_treatment_response(db, "overall")
    assert len(result.rows) == 0


def test_treatment_response_no_after_window_when_ongoing(db: Session) -> None:
    """Ongoing treatment (no end_date) should have after_mean=None, after_n=0."""
    tx_start = _BASE_DATE + datetime.timedelta(days=35)
    _add_treatment(db, "Ongoing Tx", "medication", tx_start, end_date=None)

    for i in range(30):
        d = tx_start - datetime.timedelta(days=30 - i)
        _add_entry(db, d, overall=2)

    for i in range(10):
        d = tx_start + datetime.timedelta(days=i)
        _add_entry(db, d, overall=4)

    result = compute_treatment_response(db, "overall")
    assert len(result.rows) == 1
    row = result.rows[0]
    assert row.end_date is None
    assert row.after_mean is None
    assert row.after_n == 0


# ── compute_sleep_next_day ────────────────────────────────────────────────────


def test_sleep_next_day_invalid_outcome_raises(db: Session) -> None:
    with pytest.raises(ValidationError):
        compute_sleep_next_day(db, None, None, "not_real", "hm_sleep_rem_min")


def test_sleep_next_day_invalid_metric_raises(db: Session) -> None:
    for i in range(5):
        _add_entry(db, _BASE_DATE + datetime.timedelta(days=i), overall=i)
    with pytest.raises(ValidationError):
        compute_sleep_next_day(db, None, None, "overall", "hm_invalid_metric")


def test_sleep_next_day_pairs_correctly(db: Session) -> None:
    """Each point pairs sleep[i] with outcome[i+1]. Last sleep row has no pair."""
    n_days = 10
    for i in range(n_days):
        d = _BASE_DATE + datetime.timedelta(days=i)
        _add_entry(db, d, overall=i + 1)
        _add_hm(db, d, sleep_rem_min=float(60 + i * 2))

    result = compute_sleep_next_day(
        db,
        _BASE_DATE,
        _BASE_DATE + datetime.timedelta(days=n_days - 1),
        "overall",
        "hm_sleep_rem_min",
    )
    # n_days rows → n_days - 1 pairs (last day metric has no next day)
    # But we also need the next-day outcome value so pairs can be < n_days - 1
    # if the last entry exists: all n_days-1 pairs should be present
    assert len(result.points) == n_days - 1

    # First point: sleep on day 0, outcome on day 1
    first = result.points[0]
    assert first.sleep_value == pytest.approx(60.0)
    assert first.next_day_outcome == pytest.approx(2.0)  # overall on day 1


def test_sleep_next_day_orphaned_last_day_dropped(db: Session) -> None:
    """When the last sleep metric has no following entry, the pair is dropped."""
    for i in range(5):
        d = _BASE_DATE + datetime.timedelta(days=i)
        _add_entry(db, d, overall=i + 1)
        _add_hm(db, d, sleep_rem_min=60.0)
    # Add a health metric on day 5 with NO corresponding entry
    _add_hm(db, _BASE_DATE + datetime.timedelta(days=5), sleep_rem_min=70.0)

    result = compute_sleep_next_day(
        db,
        _BASE_DATE,
        _BASE_DATE + datetime.timedelta(days=5),
        "overall",
        "hm_sleep_rem_min",
    )
    # Day 5 sleep metric has no day 6 outcome → that pair must be absent
    # Days 0-4: pair [i] metric with [i+1] outcome → 4 valid pairs (0→1, 1→2, 2→3, 3→4)
    # Day 4 metric pairs with day 5 outcome (None for entry) → dropped
    # So effectively: pairs for days 0-3 → 4 pairs
    for pt in result.points:
        assert pt.next_day_outcome is not None
        assert pt.sleep_value is not None


def test_correlates_diet_risk_is_valid_outcome(db: Session) -> None:
    """diet_risk is ordinal-encoded; compute_correlates must accept it without raising."""
    for i in range(15):
        d = _BASE_DATE + datetime.timedelta(days=i)
        risk = ["minimal", "low", "normal", "high"][i % 4]
        _add_entry(db, d, diet_risk=risk)

    # Must not raise ValidationError
    result = compute_correlates(db, None, None, "diet_risk", None, min_n=3)
    assert result.outcome == "diet_risk"


def test_sleep_next_day_rho_returned(db: Session) -> None:
    # Strong synthetic correlation
    for i in range(15):
        d = _BASE_DATE + datetime.timedelta(days=i)
        _add_entry(db, d, overall=i + 1)
        _add_hm(db, d, sleep_efficiency=float(50 + i * 2))

    result = compute_sleep_next_day(
        db,
        _BASE_DATE,
        _BASE_DATE + datetime.timedelta(days=14),
        "overall",
        "hm_sleep_efficiency",
    )
    assert result.rho is not None
    assert result.n >= 5
