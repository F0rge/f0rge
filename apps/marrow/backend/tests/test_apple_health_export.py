"""Synthetic Apple Health export fixtures for scripts.apple_health_export.

Numbers and dates in this file are invented. Do not replace them with a real export.
"""

from __future__ import annotations

import ast
import datetime
import gzip
import json
from pathlib import Path
from typing import Any, Optional

from app.schemas.health_metrics import HealthMetricCreate, HealthSamplesPayload
from scripts.apple_health_export import (
    METRIC_FIELDS,
    POST_BATCH_SIZE,
    PostFailed,
    default_end_date,
    format_counts,
    main,
    output_kind,
    parse_export,
    post_samples,
    samples_endpoint,
    write_output,
)

_START = datetime.date(2017, 1, 1)
_END = datetime.date(2017, 1, 31)
_ALLOWED_KEYS = {"date", "source", *METRIC_FIELDS}


def _rec(**attrs: str) -> str:
    parts = " ".join(f'{key}="{value}"' for key, value in attrs.items())
    return f"<Record {parts}/>"


def _export(records: list[str]) -> str:
    body = "\n".join(records)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<HealthData>\n"
        '<ExportDate value="2017-06-01 00:00:00 +0000"/>\n'
        "<Me/>\n"
        f"{body}\n"
        "</HealthData>\n"
    )


def _write_xml(directory: Path, records: list[str], name: str = "export.xml") -> Path:
    path = directory / name
    path.write_text(_export(records), encoding="utf-8")
    return path


def _qty(
    type_name: str,
    start: str,
    value: str,
    *,
    end: Optional[str] = None,
    source: str = "Apple Watch",
    unit: str = "count",
    device: str = "",
) -> str:
    attrs = {
        "type": type_name,
        "sourceName": source,
        "unit": unit,
        "startDate": start,
        "endDate": end if end is not None else start,
        "value": value,
    }
    if device:
        attrs["device"] = device
    return _rec(**attrs)


def _sleep(
    start: str,
    end: str,
    value: str,
    *,
    source: str = "Apple Watch",
    device: str = "",
) -> str:
    attrs = {
        "type": "HKCategoryTypeIdentifierSleepAnalysis",
        "sourceName": source,
        "startDate": start,
        "endDate": end,
        "value": value,
    }
    if device:
        attrs["device"] = device
    return _rec(**attrs)


def _by_date(samples: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {sample["date"]: sample for sample in samples}


def test_hrv_mean_and_sample_stdev(tmp_path: Path) -> None:
    path = _write_xml(
        tmp_path,
        [
            _qty(
                "HKQuantityTypeIdentifierHeartRateVariabilitySDNN",
                "2017-01-02 08:00:00 +0000",
                "10",
                unit="ms",
            ),
            _qty(
                "HKQuantityTypeIdentifierHeartRateVariabilitySDNN",
                "2017-01-02 12:00:00 +0000",
                "12",
                unit="ms",
            ),
            _qty(
                "HKQuantityTypeIdentifierHeartRateVariabilitySDNN",
                "2017-01-02 18:00:00 +0000",
                "14",
                unit="ms",
            ),
            _qty(
                "HKQuantityTypeIdentifierHeartRateVariabilitySDNN",
                "2017-01-03 09:00:00 +0000",
                "40",
                unit="ms",
            ),
            _qty(
                "HKQuantityTypeIdentifierHeartRate",
                "2017-01-02 09:00:00 +0000",
                "999",
                unit="count/min",
            ),
        ],
    )
    rows = _by_date(parse_export(path, _START, _END))
    assert rows["2017-01-02"]["hrv_mean"] == 12.0
    assert rows["2017-01-02"]["hrv_std"] == 2.0
    assert rows["2017-01-03"]["hrv_mean"] == 40.0
    assert rows["2017-01-03"]["hrv_std"] == 0.0
    assert "resting_hr" not in rows["2017-01-02"]
    assert all(row["source"] == "manual_import" for row in rows.values())


def test_local_date_uses_offset_and_range_is_inclusive(tmp_path: Path) -> None:
    path = _write_xml(
        tmp_path,
        [
            _qty(
                "HKQuantityTypeIdentifierRestingHeartRate",
                "2017-01-02 00:30:00 +0200",
                "50",
                unit="count/min",
            ),
            _qty(
                "HKQuantityTypeIdentifierRestingHeartRate",
                "2017-01-01 22:30:00 -0500",
                "70",
                unit="count/min",
            ),
            _qty(
                "HKQuantityTypeIdentifierRestingHeartRate",
                "2016-12-31 23:00:00 +0000",
                "11",
                unit="count/min",
            ),
            _qty(
                "HKQuantityTypeIdentifierRestingHeartRate",
                "2017-01-04 00:00:00 +0000",
                "12",
                unit="count/min",
            ),
        ],
    )
    rows = _by_date(parse_export(path, datetime.date(2017, 1, 1), datetime.date(2017, 1, 2)))
    assert set(rows) == {"2017-01-01", "2017-01-02"}
    assert rows["2017-01-02"]["resting_hr"] == 50.0
    assert rows["2017-01-01"]["resting_hr"] == 70.0


def test_resting_hr_spo2_exercise_and_wrist(tmp_path: Path) -> None:
    path = _write_xml(
        tmp_path,
        [
            _qty(
                "HKQuantityTypeIdentifierRestingHeartRate",
                "2017-01-05 08:00:00 +0000",
                "50",
                unit="count/min",
            ),
            _qty(
                "HKQuantityTypeIdentifierRestingHeartRate",
                "2017-01-05 08:05:00 +0000",
                "60",
                unit="count/min",
            ),
            _qty(
                "HKQuantityTypeIdentifierOxygenSaturation",
                "2017-01-05 08:00:00 +0000",
                "0.96",
                unit="%",
            ),
            _qty(
                "HKQuantityTypeIdentifierOxygenSaturation",
                "2017-01-05 08:10:00 +0000",
                "0.98",
                unit="%",
            ),
            _qty(
                "HKQuantityTypeIdentifierOxygenSaturation",
                "2017-01-06 08:00:00 +0000",
                "95",
                unit="%",
            ),
            _qty(
                "HKQuantityTypeIdentifierAppleExerciseTime",
                "2017-01-05 10:00:00 +0000",
                "20",
                end="2017-01-05 10:20:00 +0000",
                unit="min",
            ),
            _qty(
                "HKQuantityTypeIdentifierAppleExerciseTime",
                "2017-01-05 18:00:00 +0000",
                "90",
                end="2017-01-05 18:01:30 +0000",
                unit="s",
            ),
            _qty(
                "HKQuantityTypeIdentifierAppleExerciseTime",
                "2017-01-07 23:30:00 +0000",
                "60",
                end="2017-01-08 00:30:00 +0000",
                unit="min",
            ),
            _qty(
                "HKQuantityTypeIdentifierAppleSleepingWristTemperature",
                "2017-01-05 02:00:00 +0000",
                "-0.4",
                unit="degC",
            ),
            _qty(
                "HKQuantityTypeIdentifierAppleSleepingWristTemperature",
                "2017-01-05 03:00:00 +0000",
                "0.2",
                unit="degC",
            ),
            _qty(
                "HKQuantityTypeIdentifierActiveEnergyBurned",
                "2017-01-05 12:00:00 +0000",
                "400",
                unit="kcal",
            ),
        ],
    )
    rows = _by_date(parse_export(path, _START, _END))
    assert rows["2017-01-05"]["resting_hr"] == 55.0
    assert rows["2017-01-05"]["spo2"] == 97.0
    assert rows["2017-01-06"]["spo2"] == 95.0
    assert rows["2017-01-05"]["active_minutes"] == 21.5
    assert rows["2017-01-05"]["wrist_temp_deviation"] == -0.1
    assert "steps" not in rows["2017-01-05"]
    assert rows["2017-01-07"]["active_minutes"] == 30.0
    assert rows["2017-01-08"]["active_minutes"] == 30.0


def test_steps_prefer_watch_for_each_hour(tmp_path: Path) -> None:
    path = _write_xml(
        tmp_path,
        [
            _qty(
                "HKQuantityTypeIdentifierStepCount",
                "2017-01-09 10:00:00 +0000",
                "100",
                end="2017-01-09 11:00:00 +0000",
                source="Apple Watch",
                unit="count",
            ),
            _qty(
                "HKQuantityTypeIdentifierStepCount",
                "2017-01-09 10:00:00 +0000",
                "5000",
                end="2017-01-09 11:00:00 +0000",
                source="iPhone",
                unit="count",
            ),
            _qty(
                "HKQuantityTypeIdentifierStepCount",
                "2017-01-09 15:00:00 +0000",
                "800",
                end="2017-01-09 16:00:00 +0000",
                source="iPhone",
                unit="count",
            ),
        ],
    )
    rows = _by_date(parse_export(path, _START, _END))
    assert rows["2017-01-09"]["steps"] == 900
    assert isinstance(rows["2017-01-09"]["steps"], int)


def test_steps_split_across_hours_and_midnight(tmp_path: Path) -> None:
    path = _write_xml(
        tmp_path,
        [
            _qty(
                "HKQuantityTypeIdentifierStepCount",
                "2017-01-10 23:00:00 +0000",
                "120",
                end="2017-01-11 01:00:00 +0000",
                source="iPhone",
                unit="count",
            ),
            _qty(
                "HKQuantityTypeIdentifierStepCount",
                "2017-01-12 10:30:00 +0000",
                "100",
                end="2017-01-12 11:30:00 +0000",
                source="Health",
                device="Apple Watch",
                unit="count",
            ),
            _qty(
                "HKQuantityTypeIdentifierStepCount",
                "2017-01-12 10:00:00 +0000",
                "1000",
                end="2017-01-12 11:00:00 +0000",
                source="iPhone",
                unit="count",
            ),
            _qty(
                "HKQuantityTypeIdentifierStepCount",
                "2017-01-12 11:00:00 +0000",
                "1000",
                end="2017-01-12 12:00:00 +0000",
                source="iPhone",
                unit="count",
            ),
        ],
    )
    rows = _by_date(parse_export(path, _START, _END))
    assert rows["2017-01-10"]["steps"] == 60
    assert rows["2017-01-11"]["steps"] == 60
    assert rows["2017-01-12"]["steps"] == 100


def test_sleep_watch_preferred_on_end_date(tmp_path: Path) -> None:
    path = _write_xml(
        tmp_path,
        [
            _sleep(
                "2017-01-01 23:00:00 +0100",
                "2017-01-02 07:00:00 +0100",
                "HKCategoryValueSleepAnalysisInBed",
            ),
            _sleep(
                "2017-01-01 23:00:00 +0100",
                "2017-01-02 02:00:00 +0100",
                "HKCategoryValueSleepAnalysisAsleepCore",
            ),
            _sleep(
                "2017-01-02 02:00:00 +0100",
                "2017-01-02 03:00:00 +0100",
                "HKCategoryValueSleepAnalysisAsleepDeep",
            ),
            _sleep(
                "2017-01-02 03:00:00 +0100",
                "2017-01-02 04:00:00 +0100",
                "HKCategoryValueSleepAnalysisAsleepREM",
            ),
            _sleep(
                "2017-01-02 04:00:00 +0100",
                "2017-01-02 05:00:00 +0100",
                "HKCategoryValueSleepAnalysisAsleepCore",
            ),
            _sleep(
                "2017-01-02 05:00:00 +0100",
                "2017-01-02 07:00:00 +0100",
                "HKCategoryValueSleepAnalysisAwake",
            ),
            _sleep(
                "2017-01-01 22:00:00 +0100",
                "2017-01-02 08:00:00 +0100",
                "HKCategoryValueSleepAnalysisInBed",
                source="iPhone",
            ),
            _sleep(
                "2017-01-01 22:00:00 +0100",
                "2017-01-02 08:00:00 +0100",
                "HKCategoryValueSleepAnalysisAsleepUnspecified",
                source="iPhone",
            ),
        ],
    )
    rows = _by_date(parse_export(path, _START, _END))
    row = rows["2017-01-02"]
    assert set(rows) == {"2017-01-02"}
    assert row["sleep_hours"] == 6.0
    assert row["sleep_core_min"] == 240.0
    assert row["sleep_deep_min"] == 60.0
    assert row["sleep_rem_min"] == 60.0
    assert row["sleep_awake_min"] == 120.0
    assert row["sleep_deep_pct"] == 16.7
    assert row["sleep_rem_pct"] == 16.7
    assert row["sleep_efficiency"] == 75.0
    assert row["sleep_start"] == "2017-01-01T23:00:00+01:00"
    assert row["sleep_end"] == "2017-01-02T07:00:00+01:00"


def test_sleep_falls_back_and_unions_duplicates(tmp_path: Path) -> None:
    path = _write_xml(
        tmp_path,
        [
            _sleep(
                "2017-01-03 00:00:00 +0000",
                "2017-01-03 06:00:00 +0000",
                "HKCategoryValueSleepAnalysisInBed",
                source="iPhone",
            ),
            _sleep(
                "2017-01-03 00:00:00 +0000",
                "2017-01-03 05:00:00 +0000",
                "HKCategoryValueSleepAnalysisAsleepUnspecified",
                source="iPhone",
            ),
            _sleep(
                "2017-01-03 00:00:00 +0000",
                "2017-01-03 05:00:00 +0000",
                "HKCategoryValueSleepAnalysisAsleepUnspecified",
                source="iPhone",
            ),
        ],
    )
    row = _by_date(parse_export(path, _START, _END))["2017-01-03"]
    assert row["sleep_hours"] == 5.0
    assert row["sleep_efficiency"] == 83.3
    assert "sleep_deep_min" not in row
    assert "sleep_rem_min" not in row
    assert "sleep_core_min" not in row
    assert "sleep_deep_pct" not in row
    assert row["sleep_start"] == "2017-01-03T00:00:00+00:00"
    assert row["sleep_end"] == "2017-01-03T06:00:00+00:00"


def test_sleep_stages_ignore_unspecified_and_pick_longer_watch(tmp_path: Path) -> None:
    path = _write_xml(
        tmp_path,
        [
            _sleep(
                "2017-01-04 00:00:00 +0000",
                "2017-01-04 02:00:00 +0000",
                "HKCategoryValueSleepAnalysisAsleepCore",
                source="Watch A",
            ),
            _sleep(
                "2017-01-04 00:00:00 +0000",
                "2017-01-04 10:00:00 +0000",
                "HKCategoryValueSleepAnalysisAsleepUnspecified",
                source="Watch A",
            ),
            _sleep(
                "2017-01-04 00:00:00 +0000",
                "2017-01-04 05:00:00 +0000",
                "HKCategoryValueSleepAnalysisAsleepCore",
                source="Watch B",
            ),
            _sleep(
                "2017-01-04 00:00:00 +0000",
                "2017-01-04 09:00:00 +0000",
                "HKCategoryValueSleepAnalysisAsleepUnspecified",
                source="Other Phone",
            ),
        ],
    )
    row = _by_date(parse_export(path, _START, _END))["2017-01-04"]
    assert row["sleep_hours"] == 5.0
    assert row["sleep_core_min"] == 300.0


def test_sleep_outside_end_date_is_dropped(tmp_path: Path) -> None:
    path = _write_xml(
        tmp_path,
        [
            _sleep(
                "2017-01-01 22:00:00 +0000",
                "2017-01-02 06:00:00 +0000",
                "HKCategoryValueSleepAnalysisAsleepCore",
            ),
        ],
    )
    rows = parse_export(path, datetime.date(2017, 1, 1), datetime.date(2017, 1, 1))
    assert rows == []


def test_iterparse_keeps_every_record(tmp_path: Path) -> None:
    records = [
        _qty(
            "HKQuantityTypeIdentifierHeartRateVariabilitySDNN",
            "2017-01-15 12:00:00 +0000",
            str(index),
            unit="ms",
        )
        for index in range(1, 1001)
    ]
    path = _write_xml(tmp_path, records)
    row = parse_export(path, _START, _END)[0]
    assert row["hrv_mean"] == 500.5
    assert row["hrv_std"] != 0.0


def test_gzipped_input(tmp_path: Path) -> None:
    xml = _export(
        [
            _qty(
                "HKQuantityTypeIdentifierRestingHeartRate",
                "2017-01-16 08:00:00 +0000",
                "48",
                unit="count/min",
            )
        ]
    ).encode("utf-8")
    path = tmp_path / "export.xml.gz"
    with gzip.open(path, "wb") as handle:
        handle.write(xml)
    row = parse_export(path, _START, _END)[0]
    assert row["resting_hr"] == 48.0


def test_output_json_and_jsonl_match_samples_payload(tmp_path: Path) -> None:
    path = _write_xml(
        tmp_path,
        [
            _qty(
                "HKQuantityTypeIdentifierStepCount",
                "2017-01-17 10:00:00 +0000",
                "100",
                end="2017-01-17 11:00:00 +0000",
                source="iPhone",
                unit="count",
            ),
            _qty(
                "HKQuantityTypeIdentifierRestingHeartRate",
                "2017-01-18 08:00:00 +0000",
                "52",
                unit="count/min",
            ),
        ],
    )
    samples = parse_export(path, _START, _END)
    json_path = tmp_path / "metrics.json.gz"
    jsonl_path = tmp_path / "metrics.jsonl.gz"
    write_output(json_path, samples)
    write_output(jsonl_path, samples)

    with gzip.open(json_path, "rt", encoding="utf-8") as handle:
        payload = json.load(handle)
    assert output_kind(json_path) == "json"
    HealthSamplesPayload.model_validate(payload)
    assert [HealthMetricCreate.model_validate(sample).source for sample in payload["samples"]] == [
        "manual_import",
        "manual_import",
    ]
    for sample in payload["samples"]:
        assert set(sample) <= _ALLOWED_KEYS
        assert set(sample) - {"date", "source"}

    with gzip.open(jsonl_path, "rt", encoding="utf-8") as handle:
        lines = [json.loads(line) for line in handle if line.strip()]
    assert lines == payload["samples"]
    for line in lines:
        HealthMetricCreate.model_validate(line)


def test_stdout_is_counts_only(tmp_path: Path, capsys: Any) -> None:
    export = _write_xml(
        tmp_path,
        [
            _qty(
                "HKQuantityTypeIdentifierHeartRateVariabilitySDNN",
                "2017-01-19 08:00:00 +0000",
                "42.5",
                unit="ms",
            ),
            _qty(
                "HKQuantityTypeIdentifierStepCount",
                "2017-01-20 09:00:00 +0000",
                "321",
                end="2017-01-20 10:00:00 +0000",
                source="iPhone",
                unit="count",
            ),
        ],
    )
    out = tmp_path / "out.json.gz"
    status = main(
        ["--input", str(export), "--start", "2017-01-01", "--end", "2017-01-31", "--out", str(out)]
    )
    captured = capsys.readouterr()
    assert status == 0
    assert captured.err == ""
    assert "42.5" not in captured.out
    assert "321" not in captured.out
    lines = dict(item.split("=") for item in captured.out.strip().splitlines())
    assert lines["days"] == "2"
    assert lines["hrv_mean"] == "1"
    assert lines["hrv_std"] == "1"
    assert lines["steps"] == "1"
    assert lines["resting_hr"] == "0"
    assert lines["spo2"] == "0"
    assert set(lines) == {"days", *METRIC_FIELDS}
    with gzip.open(out, "rt", encoding="utf-8") as handle:
        payload = json.load(handle)
    assert format_counts(payload["samples"]) == captured.out


def test_default_start_and_end_lag() -> None:
    assert default_end_date(datetime.date(2026, 10, 19)) == datetime.date(2026, 7, 21)


def test_default_start_drops_earlier_days(tmp_path: Path, capsys: Any) -> None:
    export = _write_xml(
        tmp_path,
        [
            _qty(
                "HKQuantityTypeIdentifierRestingHeartRate",
                "2016-12-31 12:00:00 +0000",
                "40",
                unit="count/min",
            ),
            _qty(
                "HKQuantityTypeIdentifierRestingHeartRate",
                "2017-01-01 12:00:00 +0000",
                "41",
                unit="count/min",
            ),
        ],
    )
    out = tmp_path / "out.json.gz"
    status = main(["--input", str(export), "--end", "2017-01-01", "--out", str(out)])
    assert status == 0
    assert capsys.readouterr().out.startswith("days=1\n")
    with gzip.open(out, "rt", encoding="utf-8") as handle:
        payload = json.load(handle)
    assert payload["samples"][0]["date"] == "2017-01-01"
    assert payload["samples"][0]["resting_hr"] == 41.0


def test_post_sends_bearer_batches() -> None:
    start = datetime.date(2017, 1, 1)
    samples = [
        {
            "date": (start + datetime.timedelta(days=index)).isoformat(),
            "steps": 10,
            "source": "manual_import",
        }
        for index in range(POST_BATCH_SIZE + 1)
    ]
    calls: list[Any] = []

    class _Response:
        status = 200

        def read(self) -> bytes:
            return b'{"status":"ok","dates_upserted":1}'

        def __enter__(self) -> _Response:
            return self

        def __exit__(self, *_args: object) -> bool:
            return False

    def opener(request: Any, timeout: float) -> _Response:
        calls.append((request, timeout))
        return _Response()

    batches, days = post_samples(
        samples,
        "https://api.example.com/",
        "test-token",
        opener=opener,
    )
    assert (batches, days) == (2, POST_BATCH_SIZE + 1)
    assert len(calls) == 2
    first_body = json.loads(calls[0][0].data.decode("utf-8"))
    second_body = json.loads(calls[1][0].data.decode("utf-8"))
    assert len(first_body["samples"]) == POST_BATCH_SIZE
    assert len(second_body["samples"]) == 1
    assert calls[0][0].full_url == "https://api.example.com/api/v1/health-metrics/samples"
    assert calls[0][0].get_header("Authorization") == "Bearer test-token"
    assert calls[0][1] == 120


def test_main_post_uses_bearer_and_hides_token(
    tmp_path: Path, capsys: Any, monkeypatch: Any
) -> None:
    export = _write_xml(
        tmp_path,
        [
            _qty(
                "HKQuantityTypeIdentifierRestingHeartRate",
                "2017-01-21 08:00:00 +0000",
                "53",
                unit="count/min",
            ),
            _qty(
                "HKQuantityTypeIdentifierRestingHeartRate",
                "2017-01-22 08:00:00 +0000",
                "54",
                unit="count/min",
            ),
        ],
    )
    monkeypatch.setenv("MARROW_ACCESS_TOKEN", "super-secret-token-value")
    calls: list[Any] = []

    class _Response:
        status = 200

        def read(self) -> bytes:
            return b"{}"

        def __enter__(self) -> _Response:
            return self

        def __exit__(self, *_args: object) -> bool:
            return False

    def opener(request: Any, timeout: float) -> _Response:
        calls.append(request)
        return _Response()

    monkeypatch.setattr("scripts.apple_health_export._urlopen", opener)
    out = tmp_path / "posted.json.gz"
    status = main(
        [
            "--input",
            str(export),
            "--start",
            "2017-01-01",
            "--end",
            "2017-01-31",
            "--out",
            str(out),
            "--post",
            "--base-url",
            "https://api.example.com/api/v1/health-metrics/samples",
            "--token-env",
            "MARROW_ACCESS_TOKEN",
        ]
    )
    captured = capsys.readouterr()
    assert status == 0
    assert "super-secret-token-value" not in captured.out
    assert "super-secret-token-value" not in captured.err
    assert "53" not in captured.out
    assert "posted_batches=1\nposted_days=2\n" in captured.out
    assert len(calls) == 1
    assert calls[0].get_header("Authorization") == "Bearer super-secret-token-value"
    assert calls[0].full_url.endswith("/api/v1/health-metrics/samples")
    body = json.loads(calls[0].data.decode("utf-8"))
    assert body["samples"][0]["source"] == "manual_import"
    assert body["samples"][0]["resting_hr"] == 53.0


def test_post_error_status_omits_body(tmp_path: Path, capsys: Any, monkeypatch: Any) -> None:
    import email.message
    import urllib.error

    export = _write_xml(
        tmp_path,
        [
            _qty(
                "HKQuantityTypeIdentifierRestingHeartRate",
                "2017-01-23 08:00:00 +0000",
                "55",
                unit="count/min",
            )
        ],
    )
    monkeypatch.setenv("MARROW_ACCESS_TOKEN", "super-secret-token-value")

    def opener(request: Any, timeout: float) -> Any:
        raise urllib.error.HTTPError(
            request.full_url,
            401,
            "Unauthorized",
            email.message.Message(),
            None,
        )

    monkeypatch.setattr("scripts.apple_health_export._urlopen", opener)
    status = main(
        [
            "--input",
            str(export),
            "--start",
            "2017-01-01",
            "--end",
            "2017-01-31",
            "--out",
            str(tmp_path / "out.json.gz"),
            "--post",
            "--base-url",
            "https://api.example.com",
            "--token-env",
            "MARROW_ACCESS_TOKEN",
        ]
    )
    captured = capsys.readouterr()
    assert status == 1
    assert captured.err == "post_error_status=401\n"
    assert "55" not in captured.err
    assert "super-secret-token-value" not in captured.err + captured.out


def test_missing_token_and_bad_suffix(tmp_path: Path, capsys: Any, monkeypatch: Any) -> None:
    export = _write_xml(tmp_path, [])
    monkeypatch.delenv("MARROW_ACCESS_TOKEN", raising=False)
    status = main(
        [
            "--input",
            str(export),
            "--out",
            str(tmp_path / "out.json.gz"),
            "--post",
            "--base-url",
            "https://api.example.com",
            "--token-env",
            "MARROW_ACCESS_TOKEN",
        ]
    )
    captured = capsys.readouterr()
    assert status == 2
    assert "missing token in env MARROW_ACCESS_TOKEN" in captured.err
    assert not (tmp_path / "out.json.gz").exists()

    bad = main(
        [
            "--input",
            str(export),
            "--out",
            str(tmp_path / "out.json"),
            "--end",
            "2017-01-31",
        ]
    )
    assert bad == 2
    assert "json.gz" in capsys.readouterr().err


def test_unreadable_input_does_not_echo_xml(tmp_path: Path, capsys: Any) -> None:
    broken = tmp_path / "broken.xml"
    broken.write_text('<HealthData><Record value="SECRETVALUE"', encoding="utf-8")
    status = main(
        [
            "--input",
            str(broken),
            "--end",
            "2017-01-31",
            "--out",
            str(tmp_path / "out.json.gz"),
        ]
    )
    captured = capsys.readouterr()
    assert status == 2
    assert captured.err == "input_unreadable\n"
    assert "SECRETVALUE" not in captured.err
    assert "SECRETVALUE" not in captured.out


def test_start_after_end(tmp_path: Path, capsys: Any) -> None:
    export = _write_xml(tmp_path, [])
    status = main(
        [
            "--input",
            str(export),
            "--start",
            "2017-02-01",
            "--end",
            "2017-01-01",
            "--out",
            str(tmp_path / "out.json.gz"),
        ]
    )
    assert status == 2
    assert capsys.readouterr().err == "start must be on or before end\n"


def test_samples_endpoint_joins_base_urls() -> None:
    assert (
        samples_endpoint("https://api.example.com")
        == "https://api.example.com/api/v1/health-metrics/samples"
    )
    assert (
        samples_endpoint("https://api.example.com/api/v1/")
        == "https://api.example.com/api/v1/health-metrics/samples"
    )
    assert (
        samples_endpoint("https://api.example.com/api/v1/health-metrics/samples")
        == "https://api.example.com/api/v1/health-metrics/samples"
    )


def test_empty_post_skips_network() -> None:
    def opener(*_args: object, **_kwargs: object) -> Any:
        raise AssertionError("should not post an empty sample list")

    assert post_samples([], "https://api.example.com", "test-token", opener=opener) == (0, 0)


def test_post_failed_carries_status_only() -> None:
    error = PostFailed(503)
    assert error.status == 503
    assert "503" in str(error)
    assert "value" not in str(error)


def test_script_imports_stdlib_only() -> None:
    from scripts import apple_health_export

    source = Path(apple_health_export.__file__ or "").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    allowed = {
        "__future__",
        "argparse",
        "datetime",
        "gzip",
        "json",
        "os",
        "statistics",
        "sys",
        "urllib",
        "xml",
        "pathlib",
        "typing",
    }
    assert imported <= allowed
