from __future__ import annotations

import datetime
from collections import Counter, defaultdict
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.entry import Entry
from app.models.health_metrics import HealthMetric
from app.models.photo import Photo
from app.models.photo_analysis import PhotoAnalysis
from app.models.supplement_catalog import SupplementCatalogItem
from app.models.symptom_catalog import SymptomCatalogItem
from app.models.treatment import Treatment
from app.models.weather import WeatherReading
from app.services.diet_flags import compute_photo_signal, parse_diet_risk_csv
from f0rge_db.tenant import owned_by_user
from app.utils.dates import local_today

FEATURE_SCHEMA_VERSION = 4

STATIC_COLUMNS = [
    "date",
    # Entry fields
    "overall",
    "bloating",
    "joint_pain",
    "neuro",
    "sleep_quality",
    "stress",
    "sick",
    "hot_shower",
    "alcohol_units",
    "caffeine_servings",
    "had_alcohol",
    "had_caffeine",
    # Manual diet-risk flag assertions (user-added flags not already in photo signal)
    "manual_extra_dairy",
    "manual_extra_fodmap",
    "manual_extra_gluten",
    "manual_extra_histamine",
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
    # Counts both visible and inferred ingredients — matches diet_flags._aggregate
    # so stats and the photo_signal converge on the same numbers.
    #
    # Per-meal overrides mirror diet_flags exactly: a gluten-free-confirmed meal
    # drops its gluten exposure; a lactose-free-confirmed meal contributes 0 to the
    # lactose sum (dairy_exposure and every other axis are untouched). Accumulation
    # happens inside the per-photo loop so the flag is applied per analysis.
    hist_sum = hist_max = oligos = fructose = polyols = lactose = 0
    gluten = dairy = False
    confirmed_photo_count = 0
    ingredient_count = 0

    for photo in photos:
        a = photo.analysis
        if not (a and a.status == "confirmed"):
            continue
        confirmed_photo_count += 1
        gsup = bool(a.gluten_free_confirmed)
        lsup = bool(a.lactose_free_confirmed)
        for i in a.ingredients:
            ingredient_count += 1
            h = i.histamine_score or 0
            hist_sum += h
            if h > hist_max:
                hist_max = h
            oligos += _FODMAP_LEVEL.get(i.fodmap_oligos, 0)
            fructose += _FODMAP_LEVEL.get(i.fodmap_fructose, 0)
            polyols += _FODMAP_LEVEL.get(i.fodmap_polyols, 0)
            lactose += 0 if lsup else _FODMAP_LEVEL.get(i.fodmap_lactose, 0)
            # bool() guards against None on these nullable columns
            gluten = gluten or (bool(i.contains_gluten) and not gsup)
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
        "ingredient_count": ingredient_count,
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


async def build_feature_matrix(
    db: AsyncSession,
    start_date: Optional[datetime.date],
    end_date: Optional[datetime.date],
) -> tuple[list[dict], list[str]]:
    """Return (rows, column_order). One row per calendar date in [start_date, end_date].

    Bulk-fetches all data upfront to avoid N+1 queries across the date range.
    Dates with no entry still produce a row with all entry/dietary fields as None.
    """
    if end_date is None:
        end_date = local_today()
    if start_date is None:
        earliest = (
            await db.execute(select(func.min(Entry.date)).where(owned_by_user(Entry.user_id)))
        ).scalar()
        start_date = earliest if earliest is not None else end_date

    # Clamp: start must not exceed end
    if start_date > end_date:
        start_date = end_date

    entries_q = (
        (
            await db.execute(
                select(Entry)
                .where(
                    owned_by_user(Entry.user_id),
                    Entry.date.between(start_date, end_date),
                )
                .options(
                    selectinload(Entry.photos)
                    .selectinload(Photo.analysis)
                    .selectinload(PhotoAnalysis.ingredients)
                )
            )
        )
        .scalars()
        .all()
    )
    entry_by_date: dict[datetime.date, Entry] = {e.date: e for e in entries_q}

    hm_by_date: dict[datetime.date, HealthMetric] = {
        h.date: h
        for h in (
            await db.execute(
                select(HealthMetric).where(
                    owned_by_user(HealthMetric.user_id),
                    HealthMetric.date.between(start_date, end_date),
                )
            )
        )
        .scalars()
        .all()
    }

    weather_start = start_date - datetime.timedelta(days=1)
    all_weather = (
        (
            await db.execute(
                select(WeatherReading).where(
                    owned_by_user(WeatherReading.user_id),
                    WeatherReading.date.between(weather_start, end_date),
                )
            )
        )
        .scalars()
        .all()
    )
    weather_by_date: dict[datetime.date, list[WeatherReading]] = defaultdict(list)
    for r in all_weather:
        weather_by_date[r.date].append(r)

    supp_catalog = (
        (
            await db.execute(
                select(SupplementCatalogItem)
                .where(
                    owned_by_user(SupplementCatalogItem.user_id),
                    SupplementCatalogItem.first_used_at.isnot(None),
                )
                .order_by(SupplementCatalogItem.key)
            )
        )
        .scalars()
        .all()
    )
    supp_keys = [s.key for s in supp_catalog]

    sym_catalog = (
        (
            await db.execute(
                select(SymptomCatalogItem)
                .where(
                    owned_by_user(SymptomCatalogItem.user_id),
                    SymptomCatalogItem.first_used_at.isnot(None),
                    SymptomCatalogItem.archived.is_(False),
                )
                .order_by(SymptomCatalogItem.key)
            )
        )
        .scalars()
        .all()
    )
    sym_keys = [s.key for s in sym_catalog]

    all_treatments = (
        (
            await db.execute(
                select(Treatment)
                .where(
                    owned_by_user(Treatment.user_id),
                    Treatment.start_date <= end_date,
                    (Treatment.end_date.is_(None)) | (Treatment.end_date >= start_date),
                )
                .order_by(Treatment.normalized_name)
            )
        )
        .scalars()
        .all()
    )
    tx_names = sorted({t.normalized_name for t in all_treatments})

    columns = (
        STATIC_COLUMNS
        + [f"supp_{k}" for k in supp_keys]
        + [f"tx_{n}_active" for n in tx_names]
        + [f"sym_{k}" for k in sym_keys]
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
            dietary = _compute_dietary_loads(list(entry.photos))
            taken_keys: set[str] = {
                s.strip() for s in (entry.supplements or "").split(",") if s.strip()
            }
            _user_flags = parse_diet_risk_csv(entry.diet_risk)
            _photo_flags: set[str] = compute_photo_signal(entry).flags
            # manual_extra_* = user asserted the flag AND photos didn't catch it (0/1).
            _manual_extra = {
                "dairy": "manual_extra_dairy",
                "high-fodmap": "manual_extra_fodmap",
                "gluten": "manual_extra_gluten",
                "high-histamine": "manual_extra_histamine",
            }
            row.update(
                {
                    "overall": entry.overall,
                    "bloating": entry.bloating,
                    "joint_pain": entry.joint_pain,
                    "neuro": entry.neuro,
                    "sleep_quality": entry.sleep_quality,
                    "stress": entry.stress,
                    "sick": entry.sick,
                    "hot_shower": entry.hot_shower,
                    "alcohol_units": entry.alcohol_units,
                    "caffeine_servings": entry.caffeine_servings,
                    "had_alcohol": 1 if (entry.alcohol_units or 0) > 0 else 0,
                    "had_caffeine": 1 if (entry.caffeine_servings or 0) > 0 else 0,
                    **{
                        col: 1 if flag in _user_flags and flag not in _photo_flags else 0
                        for flag, col in _manual_extra.items()
                    },
                    "stool_status": entry.stool_status,
                    "bristol_type": entry.bristol_type,
                    "period_of_day": entry.period_of_day,
                    "schema_version": entry.schema_version,
                    **dietary,
                }
            )
            for k in supp_keys:
                row[f"supp_{k}"] = k in taken_keys

            row_symptoms = getattr(entry, "symptoms_json", {}) or {}
            for k in sym_keys:
                row[f"sym_{k}"] = row_symptoms.get(k)

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
