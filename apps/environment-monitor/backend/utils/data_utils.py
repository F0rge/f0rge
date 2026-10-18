"""Analytics helpers for sensor time-series data.

All functions take an already-filtered list of readings (as returned by
SensorService.get_historical_data(range)) and compute stats / CSV / etc.

The previous version of this module also did the time-window filtering and
uniform downsampling; that logic has moved into SensorService (SQL-backed),
so filter_historical_data() is now a pass-through kept only for backward
compat with any caller that still invokes it.
"""
from __future__ import annotations

import csv
import math
from io import StringIO
from typing import Any

from config import (
    COMFORT_TEMP_MIN,
    COMFORT_TEMP_MAX,
    COMFORT_HUMIDITY_MIN,
    COMFORT_HUMIDITY_MAX,
)


def filter_historical_data(
    historical_data: list[dict[str, Any]], time_range: str
) -> list[dict[str, Any]]:
    """Pass-through. SensorService now applies time-window filtering at the
    SQL layer, so this function just returns its input unchanged.
    Kept so that any external caller of the previous API still works.
    """
    return historical_data


def generate_csv_data(historical_data: list[dict[str, Any]]) -> str:
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["Timestamp", "Temperature (°C)", "Humidity (%)"])
    for entry in historical_data:
        writer.writerow(
            [entry["timestamp"], entry["temperature"], entry["humidity"]]
        )
    csv_data = output.getvalue()
    output.close()
    return csv_data


def calculate_averages(
    historical_data: list[dict[str, Any]], time_range: str
) -> dict[str, Any]:
    if not historical_data:
        return {
            "temperature_average": 0.0,
            "humidity_average": 0.0,
            "timeframe": time_range,
            "data_points": 0,
        }

    count = len(historical_data)
    temp_sum = sum(e["temperature"] for e in historical_data)
    humidity_sum = sum(e["humidity"] for e in historical_data)
    return {
        "temperature_average": round(temp_sum / count, 2),
        "humidity_average": round(humidity_sum / count, 2),
        "timeframe": time_range,
        "data_points": count,
    }


def calculate_enhanced_averages(
    historical_data: list[dict[str, Any]], time_range: str
) -> dict[str, Any]:
    if not historical_data:
        return {
            "temperature_average": 0.0,
            "temperature_min": 0.0,
            "temperature_max": 0.0,
            "humidity_average": 0.0,
            "humidity_min": 0.0,
            "humidity_max": 0.0,
            "timeframe": time_range,
            "data_points": 0,
        }

    temps = [e["temperature"] for e in historical_data]
    hums = [e["humidity"] for e in historical_data]
    count = len(historical_data)
    return {
        "temperature_average": round(sum(temps) / count, 2),
        "temperature_min": round(min(temps), 2),
        "temperature_max": round(max(temps), 2),
        "humidity_average": round(sum(hums) / count, 2),
        "humidity_min": round(min(hums), 2),
        "humidity_max": round(max(hums), 2),
        "timeframe": time_range,
        "data_points": count,
    }


def calculate_comprehensive_metrics(
    historical_data: list[dict[str, Any]], time_range: str
) -> dict[str, Any]:
    if not historical_data:
        return {
            "temperature_average": 0.0,
            "temperature_min": 0.0,
            "temperature_max": 0.0,
            "temperature_std_dev": 0.0,
            "humidity_average": 0.0,
            "humidity_min": 0.0,
            "humidity_max": 0.0,
            "humidity_std_dev": 0.0,
            "time_in_optimal_range": 0.0,
            "temperature_trend": "stable",
            "humidity_trend": "stable",
            "timeframe": time_range,
            "data_points": 0,
        }

    temps = [e["temperature"] for e in historical_data]
    hums = [e["humidity"] for e in historical_data]
    count = len(historical_data)

    temp_avg = sum(temps) / count
    hum_avg = sum(hums) / count
    temp_std = calculate_std_dev(temps, temp_avg)
    hum_std = calculate_std_dev(hums, hum_avg)

    optimal_count = sum(
        1 for i in range(count)
        if COMFORT_TEMP_MIN <= temps[i] <= COMFORT_TEMP_MAX
        and COMFORT_HUMIDITY_MIN <= hums[i] <= COMFORT_HUMIDITY_MAX
    )
    time_in_optimal_range = (optimal_count / count) * 100

    return {
        "temperature_average": round(temp_avg, 2),
        "temperature_min": round(min(temps), 2),
        "temperature_max": round(max(temps), 2),
        "temperature_std_dev": round(temp_std, 2),
        "humidity_average": round(hum_avg, 2),
        "humidity_min": round(min(hums), 2),
        "humidity_max": round(max(hums), 2),
        "humidity_std_dev": round(hum_std, 2),
        "time_in_optimal_range": round(time_in_optimal_range, 1),
        "temperature_trend": calculate_trend(temps, "temperature"),
        "humidity_trend": calculate_trend(hums, "humidity"),
        "timeframe": time_range,
        "data_points": count,
    }


def calculate_metrics_from_aggregate(
    agg: dict[str, Any], trend_data: list[dict[str, Any]], time_range: str
) -> dict[str, Any]:
    """Build the AverageMetrics response from a SQL-side aggregate.

    Stats (min/max/avg/std-dev/optimal%) come from the full-resolution aggregate.
    Trends are derived from a downsampled series (passed in) since they only
    need the first-vs-last comparison.
    """
    count = agg["count"]
    if count == 0:
        return {
            "temperature_average": 0.0, "temperature_min": 0.0, "temperature_max": 0.0,
            "temperature_std_dev": 0.0, "humidity_average": 0.0, "humidity_min": 0.0,
            "humidity_max": 0.0, "humidity_std_dev": 0.0, "time_in_optimal_range": 0.0,
            "temperature_trend": "stable", "humidity_trend": "stable",
            "timeframe": time_range, "data_points": 0,
        }

    t_avg = agg["temperature_avg"]
    h_avg = agg["humidity_avg"]
    # variance = E[X^2] - E[X]^2, sample variance scales by N/(N-1).
    if count > 1:
        t_var = max(0.0, (agg["temperature_sqsum"] / count) - t_avg * t_avg) * count / (count - 1)
        h_var = max(0.0, (agg["humidity_sqsum"] / count) - h_avg * h_avg) * count / (count - 1)
        t_std = math.sqrt(t_var)
        h_std = math.sqrt(h_var)
    else:
        t_std = h_std = 0.0

    temps = [e["temperature"] for e in trend_data] if trend_data else []
    hums = [e["humidity"] for e in trend_data] if trend_data else []
    return {
        "temperature_average": round(t_avg, 2),
        "temperature_min": round(agg["temperature_min"], 2),
        "temperature_max": round(agg["temperature_max"], 2),
        "temperature_std_dev": round(t_std, 2),
        "humidity_average": round(h_avg, 2),
        "humidity_min": round(agg["humidity_min"], 2),
        "humidity_max": round(agg["humidity_max"], 2),
        "humidity_std_dev": round(h_std, 2),
        "time_in_optimal_range": round((agg["optimal_count"] / count) * 100, 1),
        "temperature_trend": calculate_trend(temps, "temperature"),
        "humidity_trend": calculate_trend(hums, "humidity"),
        "timeframe": time_range,
        "data_points": count,
    }


def calculate_std_dev(values: list[float], mean: float) -> float:
    if len(values) <= 1:
        return 0.0
    variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
    return math.sqrt(variance)


def calculate_trend(values: list[float], kind: str = "temperature") -> str:
    if len(values) < 2:
        return "stable"

    n = len(values)
    first_size = max(1, n // 5)
    last_size = max(1, n // 5)
    first_avg = sum(values[:first_size]) / first_size
    last_avg = sum(values[-last_size:]) / last_size

    change = last_avg - first_avg

    # When first_avg ≈ 0, percent change explodes; fall back to absolute delta
    # with a sensible per-metric threshold (0.5°C for temp, 2% for humidity).
    if abs(first_avg) < 1e-3:
        abs_threshold = 0.5 if kind == "temperature" else 2.0
        if abs(change) < abs_threshold:
            return "stable"
        return "rising" if change > 0 else "falling"

    percent_change = abs(change / first_avg) * 100
    threshold = 0.5
    if percent_change < threshold:
        return "stable"
    return "rising" if change > 0 else "falling"
