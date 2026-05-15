from __future__ import annotations

import datetime
from collections import Counter, defaultdict
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.models.entry import Entry
from app.models.health_metrics import HealthMetric
from app.models.photo import Photo
from app.models.photo_analysis import PhotoAnalysis
from app.models.photo_ingredient import PhotoIngredient
from app.models.supplement_catalog import SupplementCatalogItem
from app.models.treatment import Treatment
from app.models.weather import WeatherReading

FEATURE_SCHEMA_VERSION = 1

STATIC_COLUMNS = [
    "date",
    # Entry fields
    "overall",
    "bloating",
    "joint_pain",
    "neuro",
    "sleep_quality",
    "stress",
    "diet_risk",
    "sick",
    "hot_shower",
    "alcohol_units",
    "caffeine_servings",
    "had_alcohol",
    "had_caffeine",
    "stool_status",
    "bristol_type",
    "period_of_day",
    "schema_version",
    # HealthMetric fields (hm_ prefix)
    "hm_hrv_mean",
    "hm_hrv_std",
    "hm_resting_hr",
    "hm_sleep_hours",
    "hm_sleep_deep_min",
    "hm_sleep_rem_min",
    "hm_sleep_core_min",
    "hm_sleep_awake_min",
    "hm_sleep_deep_pct",
    "hm_sleep_rem_pct",
    "hm_sleep_efficiency",
    "hm_sleep_start",
    "hm_sleep_end",
    "hm_steps",
    "hm_active_minutes",
    "hm_spo2",
    "hm_wrist_temp_deviation",
    # Weather fields (wx_ prefix)
    "wx_temp_mean",
    "wx_temp_min",
    "wx_temp_max",
    "wx_humidity_mean",
    "wx_pressure_mean",
    "wx_pressure_delta",
    "wx_condition",
    # Dietary load aggregates
    "histamine_load_sum",
    "histamine_load_max",
    "fodmap_oligos_sum",
    "fodmap_fructose_sum",
    "fodmap_polyols_sum",
    "fodmap_lactose_sum",
    "gluten_exposure",
    "dairy_exposure",
    "photo_count",
    "ingredient_count",
]

_FODMAP_LEVEL: dict[Optional[str], int] = {"high": 2, "moderate": 1, None: 0}


def _compute_dietary_loads(photos: list[Photo]) -> dict:
    visible: list[PhotoIngredient] = []
    confirmed_photo_count = 0

    for photo in photos:
        if photo.analysis and photo.analysis.status == "confirmed":
            confirmed_photo_count += 1
            for ing in photo.analysis.ingredients:
                if ing.visible:
                    visible.append(ing)

    hist_sum = hist_max = oligos = fructose = polyols = lactose = 0
    gluten = dairy = False
    for i in visible:
        h = i.histamine_score or 0
        hist_sum += h
        if h > hist_max:
            hist_max = h
        oligos += _FODMAP_LEVEL.get(i.fodmap_oligos, 0)
        fructose += _FODMAP_LEVEL.get(i.fodmap_fructose, 0)
        polyols += _FODMAP_LEVEL.get(i.fodmap_polyols, 0)
        lactose += _FODMAP_LEVEL.get(i.fodmap_lactose, 0)
        # bool() guards against None on these nullable columns
        gluten = gluten or bool(i.contains_gluten)
        dairy = dairy or bool(i.contains_dairy)

    return {
        "histamine_load_sum": hist_sum,
        "histamine_load_max": hist_max,
        "fodmap_oligos_sum": oligos,
        "fodmap_fructose_sum": fructose,
        "fodmap_polyols_sum": polyols,
        "fodmap_lactose_sum": lactose,
        "gluten_exposure": gluten,
        "dairy_exposure": dairy,
        "photo_count": confirmed_photo_count,
        "ingredient_count": len(visible),
    }


def _aggregate_weather(
    readings: list[WeatherReading],
    yesterday_readings: list[WeatherReading],
) -> dict:
    if not readings:
        return {
            "wx_temp_mean": None,
            "wx_temp_min": None,
            "wx_temp_max": None,
            "wx_humidity_mean": None,
            "wx_pressure_mean": None,
            "wx_pressure_delta": None,
            "wx_condition": None,
        }

    temps = [r.temperature_c for r in readings]
    humidities = [r.humidity_pct for r in readings]
    pressures = [r.pressure_hpa for r in readings]
    pressure_mean = sum(pressures) / len(pressures)

    wx_pressure_delta = None
    if yesterday_readings:
        yp = [r.pressure_hpa for r in yesterday_readings]
        wx_pressure_delta = round(pressure_mean - sum(yp) / len(yp), 2)

    conditions = Counter(r.weather_main for r in readings if r.weather_main)
    wx_condition = conditions.most_common(1)[0][0] if conditions else None

    return {
        "wx_temp_mean": round(sum(temps) / len(temps), 2),
        "wx_temp_min": round(min(temps), 2),
        "wx_temp_max": round(max(temps), 2),
        "wx_humidity_mean": round(sum(humidities) / len(humidities), 2),
        "wx_pressure_mean": round(pressure_mean, 2),
        "wx_pressure_delta": wx_pressure_delta,
        "wx_condition": wx_condition,
    }


def build_feature_matrix(
    db: Session,
    start_date: Optional[datetime.date],
    end_date: Optional[datetime.date],
) -> tuple[list[dict], list[str]]:
    """Return (rows, column_order). One row per calendar date in [start_date, end_date].

    Bulk-fetches all data upfront to avoid N+1 queries across the date range.
    Dates with no entry still produce a row with all entry/dietary fields as None.
    """
    if end_date is None:
        end_date = datetime.date.today()
    if start_date is None:
        earliest = db.query(func.min(Entry.date)).scalar()
        start_date = earliest if earliest is not None else end_date

    # Clamp: start must not exceed end
    if start_date > end_date:
        start_date = end_date

    entries_q = (
        db.query(Entry)
        .filter(Entry.date.between(start_date, end_date))
        .options(
            selectinload(Entry.photos)
            .selectinload(Photo.analysis)
            .selectinload(PhotoAnalysis.ingredients)
        )
        .all()
    )
    entry_by_date: dict[datetime.date, Entry] = {e.date: e for e in entries_q}

    hm_by_date: dict[datetime.date, HealthMetric] = {
        h.date: h
        for h in db.query(HealthMetric)
        .filter(HealthMetric.date.between(start_date, end_date))
        .all()
    }

    weather_start = start_date - datetime.timedelta(days=1)
    all_weather = (
        db.query(WeatherReading)
        .filter(WeatherReading.date.between(weather_start, end_date))
        .all()
    )
    weather_by_date: dict[datetime.date, list[WeatherReading]] = defaultdict(list)
    for r in all_weather:
        weather_by_date[r.date].append(r)

    supp_catalog = (
        db.query(SupplementCatalogItem)
        .filter(SupplementCatalogItem.first_used_at.isnot(None))
        .order_by(SupplementCatalogItem.key)
        .all()
    )
    supp_keys = [s.key for s in supp_catalog]

    all_treatments = (
        db.query(Treatment)
        .filter(
            Treatment.start_date <= end_date,
            (Treatment.end_date.is_(None)) | (Treatment.end_date >= start_date),
        )
        .order_by(Treatment.normalized_name)
        .all()
    )
    tx_names = sorted({t.normalized_name for t in all_treatments})

    columns = (
        STATIC_COLUMNS
        + [f"supp_{k}" for k in supp_keys]
        + [f"tx_{n}_active" for n in tx_names]
    )

    rows: list[dict] = []
    current = start_date
    one_day = datetime.timedelta(days=1)

    while current <= end_date:
        entry = entry_by_date.get(current)
        hm = hm_by_date.get(current)
        wx_agg = _aggregate_weather(
            weather_by_date.get(current, []),
            weather_by_date.get(current - one_day, []),
        )

        # Pre-fill every column with None; populate only what exists
        row: dict = {col: None for col in columns}
        row["date"] = current.isoformat()

        if entry is not None:
            dietary = _compute_dietary_loads(entry.photos)
            taken_keys: set[str] = {
                s.strip() for s in (entry.supplements or "").split(",") if s.strip()
            }
            row.update(
                {
                    "overall": entry.overall,
                    "bloating": entry.bloating,
                    "joint_pain": entry.joint_pain,
                    "neuro": entry.neuro,
                    "sleep_quality": entry.sleep_quality,
                    "stress": entry.stress,
                    "diet_risk": entry.diet_risk,
                    "sick": entry.sick,
                    "hot_shower": entry.hot_shower,
                    "alcohol_units": entry.alcohol_units,
                    "caffeine_servings": entry.caffeine_servings,
                    "had_alcohol": 1 if (entry.alcohol_units or 0) > 0 else 0,
                    "had_caffeine": 1 if (entry.caffeine_servings or 0) > 0 else 0,
                    "stool_status": entry.stool_status,
                    "bristol_type": entry.bristol_type,
                    "period_of_day": entry.period_of_day,
                    "schema_version": entry.schema_version,
                    **dietary,
                }
            )
            for k in supp_keys:
                row[f"supp_{k}"] = k in taken_keys

        if hm is not None:
            row.update(
                {
                    "hm_hrv_mean": hm.hrv_mean,
                    "hm_hrv_std": hm.hrv_std,
                    "hm_resting_hr": hm.resting_hr,
                    "hm_sleep_hours": hm.sleep_hours,
                    "hm_sleep_deep_min": hm.sleep_deep_min,
                    "hm_sleep_rem_min": hm.sleep_rem_min,
                    "hm_sleep_core_min": hm.sleep_core_min,
                    "hm_sleep_awake_min": hm.sleep_awake_min,
                    "hm_sleep_deep_pct": hm.sleep_deep_pct,
                    "hm_sleep_rem_pct": hm.sleep_rem_pct,
                    "hm_sleep_efficiency": hm.sleep_efficiency,
                    "hm_sleep_start": hm.sleep_start,
                    "hm_sleep_end": hm.sleep_end,
                    "hm_steps": hm.steps,
                    "hm_active_minutes": hm.active_minutes,
                    "hm_spo2": hm.spo2,
                    "hm_wrist_temp_deviation": hm.wrist_temp_deviation,
                }
            )

        active_tx = {
            t.normalized_name
            for t in all_treatments
            if t.start_date <= current and (t.end_date is None or t.end_date >= current)
        }
        for n in tx_names:
            row[f"tx_{n}_active"] = n in active_tx

        row.update(wx_agg)
        rows.append(row)
        current += one_day

    return rows, columns
