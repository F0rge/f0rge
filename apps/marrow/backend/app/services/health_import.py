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
    step_values: dict[str, list[float]] = defaultdict(list)
    spo2_values: dict[str, list[float]] = defaultdict(list)
    active_energy_values: dict[str, list[float]] = defaultdict(list)
    wrist_temp_values: dict[str, list[float]] = defaultdict(list)
    sleep_deep_pcts: dict[str, list[float]] = defaultdict(list)
    sleep_rem_pcts: dict[str, list[float]] = defaultdict(list)
    sleep_deep_mins: dict[str, list[float]] = defaultdict(list)
    sleep_rem_mins: dict[str, list[float]] = defaultdict(list)
    sleep_core_mins: dict[str, list[float]] = defaultdict(list)
    sleep_awake_mins: dict[str, list[float]] = defaultdict(list)
    sleep_efficiency_vals: dict[str, list[float]] = defaultdict(list)
    sleep_starts: dict[str, str] = {}
    sleep_ends: dict[str, str] = {}

    # Log all metric names for debugging
    metric_names = [m.get("name", "") for m in metrics_list]
    logger.info("Health Auto Export metrics received: %s", metric_names)

    for metric in metrics_list:
        name = metric.get("name", "").lower().replace(" ", "_")
        samples = metric.get("data", [])

        # Handle sleep analysis separately (different structure)
        # Exclude wrist/temperature metrics that happen to contain "sleep" in their name
        if "sleep" in name.lower() and "temp" not in name and "wrist" not in name:
            logger.info(
                "Sleep metric '%s' with %d samples, first sample keys: %s",
                name,
                len(samples),
                list(samples[0].keys()) if samples else [],
            )
            for sample in samples:
                date_str = sample.get(
                    "date",
                    sample.get("sleepEnd", sample.get("endDate", sample.get("sleepStart", ""))),
                )
                parsed_date = _parse_date(str(date_str))
                if parsed_date is None:
                    continue
                date_key = parsed_date.isoformat()

                # Extract stage durations — detect if hours or minutes
                # Health Auto Export sends stages in hours (e.g. deep=0.58)
                # when totalSleep is also in hours, or in minutes (e.g. deep=52)
                # when totalSleep is in minutes. Detect by checking if sum < 24.
                deep_raw = sample.get("deep")
                rem_raw = sample.get("rem")
                core_raw = sample.get("core")
                awake_raw = sample.get("awake")

                stage_vals = [float(v) for v in [deep_raw, rem_raw, core_raw] if v is not None]
                stage_sum = sum(stage_vals)

                # If stage values sum to < 24, they're in hours — convert to minutes
                in_hours = stage_sum > 0 and stage_sum < 24

                def to_min(val: float) -> float:
                    return val * 60.0 if in_hours else val

                if deep_raw is not None:
                    sleep_deep_mins[date_key].append(to_min(float(deep_raw)))
                if rem_raw is not None:
                    sleep_rem_mins[date_key].append(to_min(float(rem_raw)))
                if core_raw is not None:
                    sleep_core_mins[date_key].append(to_min(float(core_raw)))
                if awake_raw is not None:
                    sleep_awake_mins[date_key].append(to_min(float(awake_raw)))

                # Compute percentages (unit-agnostic since we use ratios)
                total_stage = sum(float(v) for v in [deep_raw, rem_raw, core_raw] if v is not None)
                if total_stage > 0:
                    sleep_deep_pcts[date_key].append(float(deep_raw or 0) / total_stage * 100)
                    sleep_rem_pcts[date_key].append(float(rem_raw or 0) / total_stage * 100)

                # Sleep efficiency
                in_bed = sample.get("inBed") or sample.get("inBedDuration")
                asleep_total = sample.get("totalSleep") or sample.get("asleep")
                if in_bed and asleep_total and float(in_bed) > 0:
                    ib = float(in_bed)
                    at = float(asleep_total)
                    # Both should be in the same unit; efficiency is just ratio
                    if ib > 0:
                        sleep_efficiency_vals[date_key].append(at / ib * 100)

                # Bed/wake times (keep the latest sleep session per date)
                sleep_start_str = sample.get("sleepStart") or sample.get("startDate")
                sleep_end_str = sample.get("sleepEnd") or sample.get("endDate")
                if sleep_start_str:
                    sleep_starts[date_key] = str(sleep_start_str)
                if sleep_end_str:
                    sleep_ends[date_key] = str(sleep_end_str)
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
            elif name == "step_count":
                step_values[date_key].append(qty)
            elif name in (
                "blood_oxygen",
                "oxygen_saturation",
                "blood_oxygen_saturation",
                "spo2",
            ):
                spo2_values[date_key].append(qty)
            elif name == "active_energy_burned":
                active_energy_values[date_key].append(qty)
            elif name in ("wrist_temperature", "apple_sleeping_wrist_temperature"):
                wrist_temp_values[date_key].append(qty)

    # Collect all dates
    all_dates: set[str] = set()
    for d in (
        hrv_values,
        resting_hr_values,
        step_values,
        spo2_values,
        active_energy_values,
        wrist_temp_values,
        sleep_deep_pcts,
        sleep_rem_pcts,
        sleep_deep_mins,
        sleep_rem_mins,
        sleep_core_mins,
        sleep_awake_mins,
        sleep_efficiency_vals,
    ):
        all_dates.update(d.keys())
    all_dates.update(sleep_starts.keys())
    all_dates.update(sleep_ends.keys())

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

        stage_total_min = sum(
            sum(lst)
            for lst in [
                sleep_deep_mins[date_key],
                sleep_rem_mins[date_key],
                sleep_core_mins[date_key],
            ]
        )
        sleep_hours = round(stage_total_min / 60, 2) if stage_total_min > 0 else None

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
            wrist_temp_deviation = round(statistics.mean(wrist_temp_values[date_key]), 2)

        sleep_deep_pct = None
        if sleep_deep_pcts[date_key]:
            sleep_deep_pct = round(statistics.mean(sleep_deep_pcts[date_key]), 1)

        sleep_rem_pct = None
        if sleep_rem_pcts[date_key]:
            sleep_rem_pct = round(statistics.mean(sleep_rem_pcts[date_key]), 1)

        sleep_deep_min = (
            round(sum(sleep_deep_mins[date_key]), 1) if sleep_deep_mins[date_key] else None
        )
        sleep_rem_min = (
            round(sum(sleep_rem_mins[date_key]), 1) if sleep_rem_mins[date_key] else None
        )
        sleep_core_min = (
            round(sum(sleep_core_mins[date_key]), 1) if sleep_core_mins[date_key] else None
        )
        sleep_awake_min = (
            round(sum(sleep_awake_mins[date_key]), 1) if sleep_awake_mins[date_key] else None
        )
        sleep_efficiency = (
            round(statistics.mean(sleep_efficiency_vals[date_key]), 1)
            if sleep_efficiency_vals[date_key]
            else None
        )
        sleep_start = sleep_starts.get(date_key)
        sleep_end = sleep_ends.get(date_key)

        result[date_key] = HealthMetricCreate(
            date=parsed,
            hrv_mean=hrv_mean,
            hrv_std=hrv_std,
            resting_hr=resting_hr,
            sleep_hours=sleep_hours,
            sleep_deep_min=sleep_deep_min,
            sleep_rem_min=sleep_rem_min,
            sleep_core_min=sleep_core_min,
            sleep_awake_min=sleep_awake_min,
            sleep_deep_pct=sleep_deep_pct,
            sleep_rem_pct=sleep_rem_pct,
            sleep_efficiency=sleep_efficiency,
            sleep_start=sleep_start,
            sleep_end=sleep_end,
            steps=steps,
            spo2=spo2,
            active_minutes=active_minutes,
            wrist_temp_deviation=wrist_temp_deviation,
        )

    return result
