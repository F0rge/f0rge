from __future__ import annotations

import datetime
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from f0rge_core.exceptions import ValidationError

DEFAULT_TIMEZONE = "Africa/Johannesburg"
MIN_INTERVAL = datetime.timedelta(minutes=15)
MAX_LOOKAHEAD = datetime.timedelta(days=400)

CADENCE_PRESETS: dict[str, str] = {
    "weekdays_08": "0 8 * * 1-5",
    "daily_08": "0 8 * * *",
    "weekly_mon_08": "0 8 * * 1",
    "hourly": "0 * * * *",
}

PRESET_LABELS: dict[str, str] = {
    "weekdays_08": "Weekdays 08:00",
    "daily_08": "Daily 08:00",
    "weekly_mon_08": "Mondays 08:00",
    "hourly": "Hourly",
}


def utcnow() -> datetime.datetime:
    return datetime.datetime.utcnow()


def validate_timezone(name: str) -> str:
    stripped = name.strip()
    if not stripped:
        raise ValidationError("Timezone is required")
    try:
        ZoneInfo(stripped)
    except ZoneInfoNotFoundError as exc:
        raise ValidationError("Unknown timezone") from exc
    return stripped


def resolve_cron(cadence: str) -> str:
    key = cadence.strip()
    if key in CADENCE_PRESETS:
        return CADENCE_PRESETS[key]
    return _validate_cron_expr(key)


def cadence_is_preset(cadence: str) -> bool:
    return cadence.strip() in CADENCE_PRESETS


def _validate_cron_expr(expr: str) -> str:
    parts = expr.split()
    if len(parts) != 5:
        raise ValidationError("Custom cadence must be a 5-field cron expression")
    _expand_field(parts[0], 0, 59)
    _expand_field(parts[1], 0, 23)
    _expand_field(parts[2], 1, 31)
    _expand_field(parts[3], 1, 12)
    _expand_field(parts[4], 0, 7, wrap_seven=True)
    return " ".join(parts)


def _expand_field(
    expr: str,
    minimum: int,
    maximum: int,
    *,
    wrap_seven: bool = False,
) -> set[int]:
    values: set[int] = set()
    for chunk in expr.split(","):
        piece = chunk.strip()
        if not piece:
            raise ValidationError("Invalid cron field")
        step = 1
        range_part = piece
        if "/" in piece:
            range_part, step_text = piece.split("/", 1)
            try:
                step = int(step_text)
            except ValueError as exc:
                raise ValidationError("Invalid cron step") from exc
            if step < 1:
                raise ValidationError("Invalid cron step")
        if range_part == "*":
            start, end = minimum, maximum
        elif "-" in range_part:
            start_text, end_text = range_part.split("-", 1)
            try:
                start, end = int(start_text), int(end_text)
            except ValueError as exc:
                raise ValidationError("Invalid cron range") from exc
        else:
            try:
                start = end = int(range_part)
            except ValueError as exc:
                raise ValidationError("Invalid cron value") from exc
        if start > end or start < minimum or end > maximum:
            raise ValidationError("Cron value out of range")
        values.update(range(start, end + 1, step))
    if wrap_seven and 7 in values:
        values.discard(7)
        values.add(0)
    return values


def _matches(local: datetime.datetime, cron_expr: str) -> bool:
    minute, hour, day, month, dow = cron_expr.split()
    minutes = _expand_field(minute, 0, 59)
    hours = _expand_field(hour, 0, 23)
    days = _expand_field(day, 1, 31)
    months = _expand_field(month, 1, 12)
    weekdays = _expand_field(dow, 0, 7, wrap_seven=True)
    # cron weekday: 0/7 Sunday. datetime.weekday(): Monday=0 … Sunday=6
    local_dow = (local.weekday() + 1) % 7
    return (
        local.minute in minutes
        and local.hour in hours
        and local.day in days
        and local.month in months
        and local_dow in weekdays
    )


def _as_utc_naive(when: datetime.datetime) -> datetime.datetime:
    if when.tzinfo is None:
        return when
    return when.astimezone(datetime.timezone.utc).replace(tzinfo=None)


def _to_local(when: datetime.datetime, timezone_name: str) -> datetime.datetime:
    aware = _as_utc_naive(when).replace(tzinfo=datetime.timezone.utc)
    return aware.astimezone(ZoneInfo(timezone_name))


def _from_local(local: datetime.datetime) -> datetime.datetime:
    return local.astimezone(datetime.timezone.utc).replace(tzinfo=None)


def _floor_minute(when: datetime.datetime) -> datetime.datetime:
    return when.replace(second=0, microsecond=0)


def next_fire(
    cadence: str,
    timezone_name: str,
    after: datetime.datetime,
) -> Optional[datetime.datetime]:
    cron_expr = resolve_cron(cadence)
    cursor = _floor_minute(_as_utc_naive(after)) + datetime.timedelta(minutes=1)
    limit = cursor + MAX_LOOKAHEAD
    while cursor <= limit:
        local = _to_local(cursor, timezone_name)
        if _matches(local, cron_expr):
            return cursor
        cursor += datetime.timedelta(minutes=1)
    return None


def previous_fire(
    cadence: str,
    timezone_name: str,
    at: datetime.datetime,
) -> Optional[datetime.datetime]:
    cron_expr = resolve_cron(cadence)
    cursor = _floor_minute(_as_utc_naive(at))
    limit = cursor - MAX_LOOKAHEAD
    while cursor >= limit:
        local = _to_local(cursor, timezone_name)
        if _matches(local, cron_expr):
            return cursor
        cursor -= datetime.timedelta(minutes=1)
    return None


def validate_min_interval(cadence: str, timezone_name: str) -> None:
    validate_timezone(timezone_name)
    cron_expr = resolve_cron(cadence)
    if cadence_is_preset(cadence):
        return
    start = datetime.datetime(2026, 1, 1, 0, 0, 0)
    first = next_fire(cron_expr, timezone_name, start)
    if first is None:
        raise ValidationError("Cadence never fires")
    second = next_fire(cron_expr, timezone_name, first)
    if second is None:
        return
    if second - first < MIN_INTERVAL:
        raise ValidationError("Cadence cannot fire more than once every 15 minutes")


def is_due(
    *,
    cadence: str,
    timezone_name: str,
    enabled: bool,
    last_run_at: Optional[datetime.datetime],
    now: datetime.datetime,
) -> bool:
    if not enabled:
        return False
    prev = previous_fire(cadence, timezone_name, now)
    if prev is None:
        return False
    if last_run_at is None:
        return True
    return last_run_at < prev
