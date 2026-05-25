# Datetime / Timezone Convention

Source of truth: `~/.claude/projects/-Users-leo-development-health-tracker/memory/project_datetime_tz_convention.md`.

This file is the committed-to-repo subset for the PR-review bot.

## The rule

All `DateTime` columns are **tz-naive UTC**: `TIMESTAMP WITHOUT TIME ZONE` in Postgres, `Mapped[datetime]` in SQLAlchemy. No `timezone=True` on the column. Stored values are UTC wall-clock time with no tz attached.

## Why this breaks if you forget it

Frontend code typically calls `new Date().toISOString()`, which produces `2026-05-25T08:30:00.000Z` (tz-aware UTC). Pydantic v2 happily parses that into `datetime(2026, 5, 25, 8, 30, tzinfo=timezone.utc)`.

**asyncpg refuses to bind a tz-aware datetime to a tz-naive column** — it returns a 500 with `DataError: invalid input for query argument: datetime.datetime(...) (can't subtract offset-naive and offset-aware datetimes)`.

**Local SQLite + aiosqlite silently accepts tz-aware**, so the bug only surfaces against the real Postgres dev env. Always verify against `health-dev.leo-figueiredo.com` or a local Postgres testcontainer before declaring done.

## The required stripper

Subtract the UTC offset FIRST, then drop tzinfo:

```python
from datetime import datetime as _dt
from pydantic import field_validator

@field_validator("entry_time", mode="after")
@classmethod
def strip_tz(cls, v: _dt | None) -> _dt | None:
    if v is None or v.tzinfo is None:
        return v
    utc_offset = v.utcoffset()
    return (v - utc_offset).replace(tzinfo=None)
```

Notes:
- `mode="after"` — runs after type coercion so `v.tzinfo` and `v.utcoffset()` are real.
- Subtract THEN drop. Just doing `.replace(tzinfo=None)` stores the *local wall-clock* time as if it were UTC (silent 2-hour shift in Luxembourg summer).
- Returning `v` when already tz-naive is the no-op path; lets the validator chain on Optional fields.

## For `Form(...)` params that bypass Pydantic

FastAPI's `Form(...)` extraction does NOT run Pydantic validators. Apply the same subtract-then-drop logic in the **service** before constructing the ORM model. Worked example at `app/services/photos.py:103-112` (PhotoService.upload).

## Confirmed safe sites

These are known to handle tz correctly as of 2026-05-25:
- `app/schemas/entry.py` (EntryCreate, EntryUpdate)
- `app/schemas/photo.py` (PhotoMealTimeUpdate)
- `app/services/photos.py` (PhotoService.upload, photo_id Form path)

## Candidates to audit on every model-touching PR

Run: `grep -rn "Mapped\[datetime\|Mapped\[Optional\[datetime" backend/app/models/`

Not yet confirmed-safe as of 2026-05-25:
- `treatments.start_date` / `treatments.end_date`
- `labs.collected_at`
- Any `onset_time` field

Block any PR that adds a new `Mapped[datetime]` column accepting frontend input without a stripper on every input path.

## Past incidents

- **2026-05-17 morning**: `entries.entry_time` fix shipped with stripper. **PR review missed the class-of-bug audit.**
- **2026-05-17 afternoon**: `photos.meal_time` produced a 500 in prod — same bug, never patched. Two outages, same root cause, same day. See `feedback_audit_class_of_bug.md` for the rule that now prevents this.

## What block vs warn looks like

- **Block**: new `Mapped[datetime]` column accepting frontend input, no stripper anywhere on the path.
- **Block**: `.replace(tzinfo=None)` without prior offset subtraction (silent corruption).
- **Warn**: existing column without a stripper that the PR touches but doesn't worsen.
- **Nit**: stripper present but defined as a method instead of `@field_validator(..., mode="after")`.
