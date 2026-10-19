"""Stream an Apple Health ``export.xml`` into daily ``/health-metrics/samples`` rows.

Stdlib only. A multi-gigabyte export is read with
``xml.etree.ElementTree.iterparse``; each element is cleared so the tree
does not stay in memory. stdout receives aggregate counts (how many days
carry each field), never sample values, timestamps, or tokens.

Run from ``apps/marrow/backend``::

    uv run python -m scripts.apple_health_export \\
        --input export.xml \\
        --start 2017-01-01 \\
        --out metrics.json.gz

    uv run python -m scripts.apple_health_export \\
        --input export.xml --out metrics.json.gz \\
        --post --base-url https://api.marrow-health.com \\
        --token-env MARROW_ACCESS_TOKEN

Mappings (field names match ``HealthMetric`` / ``HealthMetricCreate``):

* ``HKQuantityTypeIdentifierHeartRateVariabilitySDNN`` → ``hrv_mean`` and
  ``hrv_std`` (sample standard deviation; ``0.0`` when a day has one sample)
* ``HKQuantityTypeIdentifierRestingHeartRate`` → ``resting_hr`` (daily mean)
* ``HKQuantityTypeIdentifierStepCount`` → ``steps`` (daily sum, deduped below)
* ``HKQuantityTypeIdentifierOxygenSaturation`` → ``spo2`` (daily mean, percent)
* ``HKQuantityTypeIdentifierAppleExerciseTime`` → ``active_minutes`` (daily sum)
* ``HKQuantityTypeIdentifierAppleSleepingWristTemperature`` →
  ``wrist_temp_deviation`` (daily mean, °C deviation as exported)
* ``HKCategoryTypeIdentifierSleepAnalysis`` → the sleep fields below

Dates
-----
A quantity sample uses the local calendar date of ``startDate``. The offset
on that timestamp is the zone; UTC is not applied. ``--start`` and ``--end``
are inclusive. ``--end`` defaults to today minus 90 days. Cumulative samples
(steps, exercise time) that cross local midnight are split in proportion to
elapsed seconds, and each piece keeps the local date of that piece.

Step dedup
----------
Apple Health assigns each moment to the highest-priority source that recorded
it (Apple Watch over iPhone). This script uses a coarser hour rule:

* Each ``StepCount`` sample is split across local hours in proportion to the
  seconds that fall in that hour.
* For each local hour, if any Apple Watch sample contributed, that hour's
  steps are the Watch total only. Watch means ``sourceName`` or ``device``
  contains ``watch`` (case-insensitive). Hours with no Watch data use the
  sum of every other source.
* Same-source overlaps are summed. One device's own samples do not overlap;
  overlapping Watch samples would be double-counted.
* Sub-hour gaps are not recovered. If the Watch covers part of an hour and
  the iPhone covers the rest, the whole hour uses the Watch total, which can
  under-count relative to Apple's sub-hour priority.

``steps`` is the rounded sum of those hours.

Oxygen, exercise, wrist
-----------------------
SpO2 is stored as a percent. Apple writes a fraction (``0.97`` with unit
``%``); values ``<= 1.5`` are multiplied by 100. ``AppleExerciseTime`` is
minutes (unit ``s`` / ``sec`` is converted from seconds) and is summed into
``active_minutes``. That column is exercise time here. The Health Auto
Export importer stores active-energy kilocalories under the same name.
Wrist temperature is averaged as exported (°C deviation from baseline).

Sleep
-----
Sleep intervals are attributed to the local calendar date of ``endDate``.

When several sources end on the same date, an Apple Watch source is kept
and the others are dropped. If several sources tie on that rank, the one
with more asleep time is kept. Sources are not summed, so an iPhone copy of
the same night cannot double the Watch.

Overlapping intervals of one stage are unioned. Asleep time is deep + REM +
core when any of those stages exist (``AsleepUnspecified`` and generic
``Asleep`` are then ignored). Otherwise asleep time is the unspecified union.
``sleep_hours`` is that duration in hours. Stage fields are minutes.
``sleep_deep_pct`` and ``sleep_rem_pct`` are shares of deep+REM+core, matching
``parse_health_auto_export``. ``sleep_efficiency`` is asleep / inBed × 100
when an InBed interval and an asleep interval both exist. ``sleep_start`` and
``sleep_end`` are the earliest start and latest end, ISO 8601 with the
record's offset.

Output
------
``--out`` must end with ``.json.gz`` or ``.jsonl.gz``. ``.json.gz`` is one
gzipped JSON object ``{"samples":[...]}`` — the ``POST /api/v1/health-metrics/samples``
body. ``.jsonl.gz`` is one sample object per line (the objects inside
``samples``). Every sample sets ``source`` to ``manual_import`` and omits
null metrics so a partial day does not clear columns on upsert. Input paths
ending in ``.gz`` are read as gzip.

``--post`` auth
---------------
``POST /api/v1/health-metrics/samples`` depends on ``get_current_session``
(``app/middleware/auth.py``). That dependency decodes a JWT from
``Authorization: Bearer <token>`` or from the ``ht_session`` cookie. The JWT
is the access token returned by ``POST /api/v1/auth/login`` (90-day expiry).
The static ``HEALTH_IMPORT_TOKEN`` accepted by ``POST /health-metrics/import``
is not accepted on ``/samples``. ``--post`` sends ``Authorization: Bearer``
and reads the token from the environment variable named by ``--token-env``.
The token is never printed. Days are posted in batches of 500 as
``{"samples":[...]}`` to ``{base-url}/api/v1/health-metrics/samples``.
"""

from __future__ import annotations

import argparse
import datetime
import gzip
import json
import os
import statistics
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, BinaryIO, Callable, Iterator, Optional

DEFAULT_START = datetime.date(2017, 1, 1)
END_LAG_DAYS = 90
POST_BATCH_SIZE = 500
POST_TIMEOUT_SECONDS = 120
SPO2_FRACTION_MAX = 1.5
HOURS_PER_DAY = 24
SECONDS_PER_MINUTE = 60.0
SECONDS_PER_HOUR = 3600.0
PERCENT = 100.0
SOURCE_MANUAL_IMPORT = "manual_import"
SAMPLES_PATH = "/api/v1/health-metrics/samples"
_APPLE_DT_FORMAT = "%Y-%m-%d %H:%M:%S %z"
_WATCH_MARK = "watch"
_MEAN_PLACES = 2
_MINUTE_PLACES = 1
_PERCENT_PLACES = 1

METRIC_FIELDS = (
    "hrv_mean",
    "hrv_std",
    "resting_hr",
    "sleep_hours",
    "sleep_deep_min",
    "sleep_rem_min",
    "sleep_core_min",
    "sleep_awake_min",
    "sleep_deep_pct",
    "sleep_rem_pct",
    "sleep_efficiency",
    "sleep_start",
    "sleep_end",
    "steps",
    "active_minutes",
    "spo2",
    "wrist_temp_deviation",
)

_RECORD_KINDS = {
    "HKQuantityTypeIdentifierHeartRateVariabilitySDNN": "hrv",
    "HKQuantityTypeIdentifierRestingHeartRate": "rhr",
    "HKQuantityTypeIdentifierStepCount": "steps",
    "HKQuantityTypeIdentifierOxygenSaturation": "spo2",
    "HKQuantityTypeIdentifierAppleExerciseTime": "exercise",
    "HKQuantityTypeIdentifierAppleSleepingWristTemperature": "wrist",
    "HKCategoryTypeIdentifierSleepAnalysis": "sleep",
}

_SLEEP_STAGES = (
    ("InBed", "in_bed"),
    ("Awake", "awake"),
    ("AsleepCore", "core"),
    ("AsleepDeep", "deep"),
    ("AsleepREM", "rem"),
    ("AsleepUnspecified", "unspecified"),
    ("Asleep", "unspecified"),
)
_STAGED_ASLEEP = ("core", "deep", "rem")
_SECOND_UNITS = frozenset({"s", "sec", "secs", "second", "seconds"})

Opener = Callable[[urllib.request.Request, float], Any]
_Interval = tuple[datetime.datetime, datetime.datetime]


class PostFailed(Exception):
    """HTTP or transport failure while posting a batch. Carries a status only."""

    def __init__(self, status: int) -> None:
        self.status = status
        super().__init__(f"post_error_status={status}")


class _SleepSource:
    def __init__(self, label: str, is_watch: bool) -> None:
        self.label = label
        self.is_watch = is_watch
        self.intervals: dict[str, list[_Interval]] = {}

    def add(self, stage: str, start: datetime.datetime, end: datetime.datetime) -> None:
        self.intervals.setdefault(stage, []).append((start, end))


class _Aggregator:
    def __init__(self, start: datetime.date, end: datetime.date) -> None:
        self.start = start
        self.end = end
        self.hrv: dict[datetime.date, list[float]] = {}
        self.rhr: dict[datetime.date, list[float]] = {}
        self.spo2: dict[datetime.date, list[float]] = {}
        self.wrist: dict[datetime.date, list[float]] = {}
        self.exercise: dict[datetime.date, float] = {}
        self.step_watch: dict[datetime.date, list[float]] = {}
        self.step_other: dict[datetime.date, list[float]] = {}
        self.step_watch_seen: dict[datetime.date, list[bool]] = {}
        self.sleep: dict[datetime.date, dict[str, _SleepSource]] = {}

    def add(self, attrib: dict[str, str]) -> None:
        kind = _kind_for_type(attrib.get("type", ""))
        if kind is None:
            return
        if kind == "sleep":
            self._add_sleep(attrib)
            return
        value = _parse_float(attrib.get("value"))
        if value is None:
            return
        start = _parse_apple_dt(attrib.get("startDate", ""))
        if start is None:
            return
        end = _parse_apple_dt(attrib.get("endDate", "")) or start
        if end < start:
            return
        if kind == "steps":
            if value < 0:
                return
            self._add_steps(start, end, value, _is_watch(attrib))
            return
        if kind == "exercise":
            minutes = _as_minutes(value, attrib.get("unit", ""))
            if minutes is None:
                return
            self._add_exercise(start, end, minutes)
            return
        day = start.date()
        if not self._in_range(day):
            return
        if kind == "hrv":
            if value < 0:
                return
            self.hrv.setdefault(day, []).append(value)
            return
        if kind == "rhr":
            if value < 0:
                return
            self.rhr.setdefault(day, []).append(value)
            return
        if kind == "spo2":
            percent = _spo2_percent(value)
            if percent is None:
                return
            self.spo2.setdefault(day, []).append(percent)
            return
        if kind == "wrist":
            self.wrist.setdefault(day, []).append(value)

    def samples(self) -> list[dict[str, Any]]:
        days = set(self.hrv)
        days.update(self.rhr)
        days.update(self.spo2)
        days.update(self.wrist)
        days.update(self.exercise)
        days.update(self.step_watch)
        days.update(self.sleep)
        built: list[dict[str, Any]] = []
        for day in sorted(days):
            sample = self._sample_for(day)
            if sample is not None:
                built.append(sample)
        return built

    def _in_range(self, day: datetime.date) -> bool:
        return self.start <= day <= self.end

    def _add_steps(
        self,
        start: datetime.datetime,
        end: datetime.datetime,
        value: float,
        watch: bool,
    ) -> None:
        for day, hour, fraction in _walk_local_hours(start, end):
            if not self._in_range(day):
                continue
            self._ensure_step_day(day)
            amount = value * fraction
            if watch:
                self.step_watch[day][hour] += amount
                self.step_watch_seen[day][hour] = True
            else:
                self.step_other[day][hour] += amount

    def _ensure_step_day(self, day: datetime.date) -> None:
        if day in self.step_watch:
            return
        self.step_watch[day] = [0.0] * HOURS_PER_DAY
        self.step_other[day] = [0.0] * HOURS_PER_DAY
        self.step_watch_seen[day] = [False] * HOURS_PER_DAY

    def _add_exercise(
        self,
        start: datetime.datetime,
        end: datetime.datetime,
        minutes: float,
    ) -> None:
        for day, fraction in _walk_local_dates(start, end):
            if not self._in_range(day):
                continue
            self.exercise[day] = self.exercise.get(day, 0.0) + minutes * fraction

    def _add_sleep(self, attrib: dict[str, str]) -> None:
        stage = _sleep_stage(attrib.get("value", ""))
        if stage is None:
            return
        start = _parse_apple_dt(attrib.get("startDate", ""))
        end = _parse_apple_dt(attrib.get("endDate", ""))
        if start is None or end is None or end < start:
            return
        day = end.date()
        if not self._in_range(day):
            return
        label = attrib.get("sourceName") or attrib.get("device") or "unknown"
        sources = self.sleep.setdefault(day, {})
        source = sources.get(label)
        if source is None:
            source = _SleepSource(label, _is_watch(attrib))
            sources[label] = source
        elif _is_watch(attrib):
            source.is_watch = True
        source.add(stage, start, end)

    def _sample_for(self, day: datetime.date) -> Optional[dict[str, Any]]:
        fields: dict[str, Any] = {}
        hrv = self.hrv.get(day)
        if hrv:
            fields["hrv_mean"] = round(statistics.mean(hrv), _MEAN_PLACES)
            if len(hrv) > 1:
                fields["hrv_std"] = round(statistics.stdev(hrv), _MEAN_PLACES)
            else:
                fields["hrv_std"] = 0.0
        rhr = self.rhr.get(day)
        if rhr:
            fields["resting_hr"] = round(statistics.mean(rhr), _MEAN_PLACES)
        spo2 = self.spo2.get(day)
        if spo2:
            fields["spo2"] = round(statistics.mean(spo2), _MEAN_PLACES)
        wrist = self.wrist.get(day)
        if wrist:
            fields["wrist_temp_deviation"] = round(statistics.mean(wrist), _MEAN_PLACES)
        if day in self.exercise:
            fields["active_minutes"] = round(self.exercise[day], _MEAN_PLACES)
        if day in self.step_watch:
            fields["steps"] = _steps_for_day(
                self.step_watch[day],
                self.step_other[day],
                self.step_watch_seen[day],
            )
        sleep_fields = _sleep_fields(self.sleep.get(day, {}))
        fields.update(sleep_fields)
        if not fields:
            return None
        sample: dict[str, Any] = {"date": day.isoformat()}
        for name in METRIC_FIELDS:
            if name in fields:
                sample[name] = fields[name]
        sample["source"] = SOURCE_MANUAL_IMPORT
        return sample


def parse_export(
    path: Path,
    start: datetime.date,
    end: datetime.date,
) -> list[dict[str, Any]]:
    """Aggregate ``path`` into sample objects for ``[start, end]``."""
    aggregator = _Aggregator(start, end)
    for attrib in iter_record_attribs(path):
        aggregator.add(attrib)
    return aggregator.samples()


def iter_record_attribs(path: Path) -> Iterator[dict[str, str]]:
    """Yield a copy of each ``Record`` attribute map, then clear the element."""
    with _open_xml(path) as handle:
        context = ET.iterparse(handle, events=("start", "end"))
        try:
            _, root = next(context)
        except StopIteration:
            return
        for event, elem in context:
            if event != "end":
                continue
            attrib: Optional[dict[str, str]] = None
            if _local_tag(elem.tag) == "Record":
                attrib = dict(elem.attrib)
            elem.clear()
            if elem is not root:
                root.clear()
            if attrib is not None:
                yield attrib


def default_end_date(today: Optional[datetime.date] = None) -> datetime.date:
    """Inclusive end date: today minus 90 days."""
    current = today if today is not None else datetime.date.today()
    return current - datetime.timedelta(days=END_LAG_DAYS)


def samples_endpoint(base_url: str) -> str:
    """Resolve ``base_url`` to the samples collection URL."""
    base = base_url.strip().rstrip("/")
    if base.endswith(SAMPLES_PATH):
        return base
    if base.endswith("/api/v1"):
        return base + "/health-metrics/samples"
    return base + SAMPLES_PATH


def post_samples(
    samples: list[dict[str, Any]],
    base_url: str,
    token: str,
    *,
    batch_size: int = POST_BATCH_SIZE,
    opener: Optional[Opener] = None,
) -> tuple[int, int]:
    """POST ``samples`` in batches. Returns ``(batches, days)``."""
    if not samples:
        return 0, 0
    send = opener if opener is not None else _urlopen
    url = samples_endpoint(base_url)
    batches = 0
    days = 0
    for offset in range(0, len(samples), batch_size):
        batch = samples[offset : offset + batch_size]
        _post_batch(url, token, batch, send)
        batches += 1
        days += len(batch)
    return batches, days


def write_output(path: Path, samples: list[dict[str, Any]]) -> None:
    """Write gzipped JSON (``{"samples": [...]}``) or JSONL of sample objects."""
    kind = output_kind(path)
    if kind == "jsonl":
        lines = [json.dumps(sample, allow_nan=False, separators=(",", ":")) for sample in samples]
        text = "\n".join(lines)
        if lines:
            text += "\n"
        raw = text.encode("utf-8")
    else:
        raw = json.dumps(
            {"samples": samples},
            allow_nan=False,
            separators=(",", ":"),
        ).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wb") as handle:
        handle.write(raw)


def output_kind(path: Path) -> str:
    """Return ``json`` or ``jsonl``. Raises ``ValueError`` on a bad suffix."""
    name = path.name
    if name.endswith(".jsonl.gz"):
        return "jsonl"
    if name.endswith(".json.gz"):
        return "json"
    raise ValueError("out must end with .json.gz or .jsonl.gz")


def format_counts(samples: list[dict[str, Any]]) -> str:
    """Day count plus how many days include each metric field."""
    counts = {field: 0 for field in METRIC_FIELDS}
    for sample in samples:
        for field in METRIC_FIELDS:
            if sample.get(field) is not None:
                counts[field] += 1
    lines = [f"days={len(samples)}"]
    lines.extend(f"{field}={counts[field]}" for field in METRIC_FIELDS)
    return "\n".join(lines) + "\n"


def main(argv: Optional[list[str]] = None) -> int:
    """CLI entry. Prints counts only. Returns a process status code."""
    args = _parse_args(argv)
    end = args.end if args.end is not None else default_end_date()
    if args.start > end:
        print("start must be on or before end", file=sys.stderr)
        return 2
    try:
        output_kind(args.out)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if not args.input.is_file():
        print("input_unreadable", file=sys.stderr)
        return 2
    token = ""
    if args.post:
        if not args.base_url or not args.token_env:
            print("post requires --base-url and --token-env", file=sys.stderr)
            return 2
        token = os.environ.get(args.token_env, "")
        if not token.strip():
            print(f"missing token in env {args.token_env}", file=sys.stderr)
            return 2
    try:
        samples = parse_export(args.input, args.start, end)
    except (ET.ParseError, gzip.BadGzipFile, OSError):
        print("input_unreadable", file=sys.stderr)
        return 2
    try:
        write_output(args.out, samples)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    sys.stdout.write(format_counts(samples))
    if not args.post:
        return 0
    try:
        batches, days = post_samples(samples, args.base_url, token)
    except PostFailed as exc:
        print(f"post_error_status={exc.status}", file=sys.stderr)
        return 1
    sys.stdout.write(f"posted_batches={batches}\nposted_days={days}\n")
    return 0


def _parse_args(argv: Optional[list[str]]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Aggregate an Apple Health export.xml into daily health-metrics samples. "
            "See the module docstring for field mappings, step dedup, and --post auth."
        )
    )
    parser.add_argument("--input", required=True, type=Path, help="export.xml or export.xml.gz")
    parser.add_argument(
        "--start",
        type=_cli_date,
        default=DEFAULT_START,
        help="inclusive local start date (default 2017-01-01)",
    )
    parser.add_argument(
        "--end",
        type=_cli_date,
        default=None,
        help="inclusive local end date (default: today minus 90 days)",
    )
    parser.add_argument(
        "--out",
        required=True,
        type=Path,
        help="gzipped .json.gz payload or .jsonl.gz sample lines",
    )
    parser.add_argument(
        "--post",
        action="store_true",
        help="POST samples in batches of 500 to --base-url",
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help="API origin, for example https://api.marrow-health.com",
    )
    parser.add_argument(
        "--token-env",
        default=None,
        help="name of the env var holding the login JWT (not the token itself)",
    )
    return parser.parse_args(argv)


def _cli_date(value: str) -> datetime.date:
    try:
        return datetime.date.fromisoformat(value)
    except ValueError:
        raise argparse.ArgumentTypeError("use YYYY-MM-DD") from None


def _urlopen(request: urllib.request.Request, timeout: float) -> Any:
    return urllib.request.urlopen(request, timeout=timeout)


def _post_batch(
    url: str,
    token: str,
    batch: list[dict[str, Any]],
    opener: Opener,
) -> None:
    raw = json.dumps(
        {"samples": batch},
        allow_nan=False,
        separators=(",", ":"),
    ).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=raw,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with opener(request, POST_TIMEOUT_SECONDS) as response:
            response.read()
            status = getattr(response, "status", None)
            if status is None:
                status = response.getcode()
    except urllib.error.HTTPError as exc:
        raise PostFailed(exc.code) from None
    except urllib.error.URLError:
        raise PostFailed(0) from None
    code = int(status)
    if code < 200 or code >= 300:
        raise PostFailed(code)


def _kind_for_type(type_name: str) -> Optional[str]:
    return _RECORD_KINDS.get(type_name)


def _local_tag(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def _parse_float(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value.strip())
    except ValueError:
        return None


def _parse_apple_dt(value: str) -> Optional[datetime.datetime]:
    text = value.strip()
    if not text:
        return None
    try:
        return datetime.datetime.strptime(text, _APPLE_DT_FORMAT)
    except ValueError:
        return None


def _is_watch(attrib: dict[str, str]) -> bool:
    blob = f"{attrib.get('sourceName', '')} {attrib.get('device', '')}".lower()
    return _WATCH_MARK in blob


def _spo2_percent(value: float) -> Optional[float]:
    if value < 0:
        return None
    if value <= SPO2_FRACTION_MAX:
        return value * PERCENT
    return value


def _as_minutes(value: float, unit: str) -> Optional[float]:
    if value < 0:
        return None
    if unit.strip().lower() in _SECOND_UNITS:
        return value / SECONDS_PER_MINUTE
    return value


def _sleep_stage(value: str) -> Optional[str]:
    for suffix, stage in _SLEEP_STAGES:
        if value.endswith(suffix):
            return stage
    return None


def _walk_local_hours(
    start: datetime.datetime,
    end: datetime.datetime,
) -> Iterator[tuple[datetime.date, int, float]]:
    """Yield ``(local date, hour, fraction)`` using ``start``'s offset."""
    total = (end - start).total_seconds()
    if total <= 0:
        yield start.date(), start.hour, 1.0
        return
    cursor = start
    while cursor < end:
        hour_floor = cursor.replace(minute=0, second=0, microsecond=0)
        next_hour = hour_floor + datetime.timedelta(hours=1)
        segment_end = next_hour if next_hour < end else end
        if segment_end <= cursor:
            break
        fraction = (segment_end - cursor).total_seconds() / total
        yield cursor.date(), cursor.hour, fraction
        cursor = segment_end


def _walk_local_dates(
    start: datetime.datetime,
    end: datetime.datetime,
) -> Iterator[tuple[datetime.date, float]]:
    """Yield ``(local date, fraction)`` using ``start``'s offset."""
    total = (end - start).total_seconds()
    if total <= 0:
        yield start.date(), 1.0
        return
    cursor = start
    while cursor < end:
        next_day = datetime.datetime.combine(
            cursor.date() + datetime.timedelta(days=1),
            datetime.time.min,
            tzinfo=cursor.tzinfo,
        )
        segment_end = next_day if next_day < end else end
        if segment_end <= cursor:
            break
        fraction = (segment_end - cursor).total_seconds() / total
        yield cursor.date(), fraction
        cursor = segment_end


def _union_seconds(intervals: list[_Interval]) -> float:
    if not intervals:
        return 0.0
    ordered = sorted(intervals)
    total = 0.0
    cur_start, cur_end = ordered[0]
    for start, end in ordered[1:]:
        if start <= cur_end:
            if end > cur_end:
                cur_end = end
        else:
            total += (cur_end - cur_start).total_seconds()
            cur_start, cur_end = start, end
    total += (cur_end - cur_start).total_seconds()
    return total


def _steps_for_day(
    watch: list[float],
    other: list[float],
    watch_seen: list[bool],
) -> int:
    total = 0.0
    for hour in range(HOURS_PER_DAY):
        if watch_seen[hour]:
            total += watch[hour]
        else:
            total += other[hour]
    return int(round(total))


def _asleep_seconds(source: _SleepSource) -> float:
    if _has_stages(source):
        return sum(_union_seconds(source.intervals.get(stage, [])) for stage in _STAGED_ASLEEP)
    return _union_seconds(source.intervals.get("unspecified", []))


def _has_stages(source: _SleepSource) -> bool:
    return any(source.intervals.get(stage) for stage in _STAGED_ASLEEP)


def _sleep_fields(sources: dict[str, _SleepSource]) -> dict[str, Any]:
    if not sources:
        return {}
    chosen = min(
        sources.values(),
        key=lambda source: (0 if source.is_watch else 1, -_asleep_seconds(source)),
    )
    deep_s = _union_seconds(chosen.intervals.get("deep", []))
    rem_s = _union_seconds(chosen.intervals.get("rem", []))
    core_s = _union_seconds(chosen.intervals.get("core", []))
    awake_s = _union_seconds(chosen.intervals.get("awake", []))
    unspec_s = _union_seconds(chosen.intervals.get("unspecified", []))
    inbed_s = _union_seconds(chosen.intervals.get("in_bed", []))
    staged = _has_stages(chosen)
    asleep_s = deep_s + rem_s + core_s if staged else unspec_s
    fields: dict[str, Any] = {}
    if asleep_s > 0:
        fields["sleep_hours"] = round(asleep_s / SECONDS_PER_HOUR, _MEAN_PLACES)
    if chosen.intervals.get("deep"):
        fields["sleep_deep_min"] = round(deep_s / SECONDS_PER_MINUTE, _MINUTE_PLACES)
    if chosen.intervals.get("rem"):
        fields["sleep_rem_min"] = round(rem_s / SECONDS_PER_MINUTE, _MINUTE_PLACES)
    if chosen.intervals.get("core"):
        fields["sleep_core_min"] = round(core_s / SECONDS_PER_MINUTE, _MINUTE_PLACES)
    if chosen.intervals.get("awake"):
        fields["sleep_awake_min"] = round(awake_s / SECONDS_PER_MINUTE, _MINUTE_PLACES)
    stage_total = deep_s + rem_s + core_s
    if staged and stage_total > 0:
        fields["sleep_deep_pct"] = round(deep_s / stage_total * PERCENT, _PERCENT_PLACES)
        fields["sleep_rem_pct"] = round(rem_s / stage_total * PERCENT, _PERCENT_PLACES)
    asleep_present = staged or bool(chosen.intervals.get("unspecified"))
    if inbed_s > 0 and asleep_present:
        fields["sleep_efficiency"] = round(asleep_s / inbed_s * PERCENT, _PERCENT_PLACES)
    all_intervals = [interval for group in chosen.intervals.values() for interval in group]
    if all_intervals:
        fields["sleep_start"] = min(interval[0] for interval in all_intervals).isoformat()
        fields["sleep_end"] = max(interval[1] for interval in all_intervals).isoformat()
    return fields


def _open_xml(path: Path) -> BinaryIO:
    if path.name.endswith(".gz"):
        return gzip.open(path, "rb")
    return open(path, "rb")


if __name__ == "__main__":
    raise SystemExit(main())
