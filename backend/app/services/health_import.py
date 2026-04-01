from __future__ import annotations

import datetime
import logging
import statistics
from collections import defaultdict
from typing import Optional

from app.schemas.health_metrics import HealthMetricCreate

logger = logging.getLogger(__name__)


def _parse_date(date_str: str) -> Optional[datetime.date]:
    """Parse a date string from Health Auto Export, trying common formats."""
    for fmt in ("%Y-%m-%d %H:%M:%S %z", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(date_str.strip(), fmt).date()
        except ValueError:
            continue
    # Try parsing just the first 10 chars as YYYY-MM-DD
    try:
        return datetime.date.fromisoformat(date_str[:10])
    except (ValueError, IndexError):
        return None


def parse_health_auto_export(
    payload: dict,
) -> dict[str, HealthMetricCreate]:
    """Parse a Health Auto Export payload into HealthMetricCreate objects by date.

    Expected payload structure: {"data": {"metrics": [...]}}
    Each metric: {"name": str, "units": str, "data": [{"qty": float, "date": str}, ...]}
    """
    metrics_list = payload.get("data", {}).get("metrics", [])

    # Accumulators per date
    hrv_values: dict[str, list[float]] = defaultdict(list)
    resting_hr_values: dict[str, list[float]] = defaultdict(list)
    sleep_durations: dict[str, list[float]] = defaultdict(list)
    step_values: dict[str, list[float]] = defaultdict(list)
    spo2_values: dict[str, list[float]] = defaultdict(list)
    active_energy_values: dict[str, list[float]] = defaultdict(list)
    wrist_temp_values: dict[str, list[float]] = defaultdict(list)
    sleep_deep_pcts: dict[str, list[float]] = defaultdict(list)
    sleep_rem_pcts: dict[str, list[float]] = defaultdict(list)

    # Log all metric names for debugging
    metric_names = [m.get("name", "") for m in metrics_list]
    logger.info("Health Auto Export metrics received: %s", metric_names)

    for metric in metrics_list:
        name = metric.get("name", "").lower().replace(" ", "_")
        samples = metric.get("data", [])

        # Handle sleep analysis separately (different structure)
        if "sleep" in name.lower():
            logger.info("Sleep metric '%s' with %d samples, first sample keys: %s",
                       name, len(samples), list(samples[0].keys()) if samples else [])
            for sample in samples:
                date_str = sample.get("date", sample.get("sleepStart", sample.get("startDate", "")))
                parsed_date = _parse_date(str(date_str))
                if parsed_date is None:
                    continue
                date_key = parsed_date.isoformat()

                # Try various sleep duration formats
                hours = sample.get("qty")
                if hours is None:
                    # Health Auto Export v2 format: duration fields in minutes or hours
                    total_sleep = sample.get("totalSleep")
                    if total_sleep is not None:
                        hours = float(total_sleep) / 60.0  # minutes to hours
                    elif sample.get("asleep") is not None:
                        hours = float(sample["asleep"]) / 60.0
                    elif sample.get("duration") is not None:
                        hours = float(sample["duration"]) / 3600.0  # seconds to hours
                if hours is not None:
                    sleep_durations[date_key].append(float(hours))

                # Extract deep and REM percentages
                deep = sample.get("deep")
                rem = sample.get("rem")
                core = sample.get("core")
                if deep is not None and (deep or core or rem):
                    total = (float(deep or 0) + float(rem or 0) + float(core or 0))
                    if total > 0:
                        if date_key not in sleep_deep_pcts:
                            sleep_deep_pcts[date_key] = []
                        if date_key not in sleep_rem_pcts:
                            sleep_rem_pcts[date_key] = []
                        sleep_deep_pcts[date_key].append(float(deep or 0) / total * 100)
                        sleep_rem_pcts[date_key].append(float(rem or 0) / total * 100)
            continue

        for sample in samples:
            qty = sample.get("qty")
            if qty is None:
                # Try alternate value fields
                qty = sample.get("Avg") or sample.get("value")
            if qty is None:
                continue
            try:
                qty = float(qty)
            except (ValueError, TypeError):
                continue

            date_str = sample.get("date", "")
            parsed_date = _parse_date(date_str)
            if parsed_date is None:
                continue
            date_key = parsed_date.isoformat()

            if name == "heart_rate_variability":
                hrv_values[date_key].append(qty)
            elif name == "resting_heart_rate":
                resting_hr_values[date_key].append(qty)
            elif name == "sleep_analysis":
                sleep_durations[date_key].append(qty)
            elif name == "step_count":
                step_values[date_key].append(qty)
            elif name in ("blood_oxygen", "oxygen_saturation", "blood_oxygen_saturation", "spo2"):
                spo2_values[date_key].append(qty)
            elif name == "active_energy_burned":
                active_energy_values[date_key].append(qty)
            elif name == "wrist_temperature":
                wrist_temp_values[date_key].append(qty)

    # Collect all dates
    all_dates: set[str] = set()
    for d in (
        hrv_values,
        resting_hr_values,
        sleep_durations,
        step_values,
        spo2_values,
        active_energy_values,
        wrist_temp_values,
        sleep_deep_pcts,
        sleep_rem_pcts,
    ):
        all_dates.update(d.keys())

    result: dict[str, HealthMetricCreate] = {}

    for date_key in sorted(all_dates):
        parsed = datetime.date.fromisoformat(date_key)

        hrv_mean = None
        hrv_std = None
        if hrv_values[date_key]:
            vals = hrv_values[date_key]
            hrv_mean = round(statistics.mean(vals), 2)
            hrv_std = round(statistics.stdev(vals), 2) if len(vals) > 1 else 0.0

        resting_hr = None
        if resting_hr_values[date_key]:
            resting_hr = round(statistics.mean(resting_hr_values[date_key]), 2)

        sleep_hours = None
        if sleep_durations[date_key]:
            sleep_hours = round(sum(sleep_durations[date_key]), 2)

        steps = None
        if step_values[date_key]:
            steps = int(sum(step_values[date_key]))

        spo2 = None
        if spo2_values[date_key]:
            spo2 = round(statistics.mean(spo2_values[date_key]), 2)

        active_minutes = None
        if active_energy_values[date_key]:
            # Store total active energy as a proxy
            active_minutes = round(sum(active_energy_values[date_key]), 2)

        wrist_temp_deviation = None
        if wrist_temp_values[date_key]:
            wrist_temp_deviation = round(
                statistics.mean(wrist_temp_values[date_key]), 2
            )

        sleep_deep_pct = None
        if sleep_deep_pcts[date_key]:
            sleep_deep_pct = round(statistics.mean(sleep_deep_pcts[date_key]), 1)

        sleep_rem_pct = None
        if sleep_rem_pcts[date_key]:
            sleep_rem_pct = round(statistics.mean(sleep_rem_pcts[date_key]), 1)

        result[date_key] = HealthMetricCreate(
            date=parsed,
            hrv_mean=hrv_mean,
            hrv_std=hrv_std,
            resting_hr=resting_hr,
            sleep_hours=sleep_hours,
            sleep_deep_pct=sleep_deep_pct,
            sleep_rem_pct=sleep_rem_pct,
            steps=steps,
            spo2=spo2,
            active_minutes=active_minutes,
            wrist_temp_deviation=wrist_temp_deviation,
        )

    return result
