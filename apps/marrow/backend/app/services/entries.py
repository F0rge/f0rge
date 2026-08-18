from __future__ import annotations

import asyncio
import datetime
from typing import Optional

from sqlalchemy import inspect as sa_inspect
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.entries import EntryCRUD
from app.crud.meal_tags import MealTagCRUD
from app.cache import redis_client
from app.cache.invalidation import invalidate_user_insights_cache
from app.cache.keys import entry_key
from app.config import settings
from f0rge_core.exceptions import ConflictError, NotFoundError
from app.models.entry import Entry
from app.models.photo import Photo
from app.schemas.entry import EntryCreate, EntryResponse, EntryStatsResponse, EntryUpdate
from app.schemas.photo import PhotoResponse
from app.services.diet_flags import (
    compute_photo_signal,
    compute_signal_from_analyses,
    parse_diet_risk_csv,
)
from app.services.photo_storage import delete_photo
from app.utils.dates import local_today
from f0rge_db.tenant import current_user_id

# Bump whenever Entry's column shape changes; both entry-creation paths below
# (form submit and photo-first skeleton) must always stamp the same value.
CURRENT_SCHEMA_VERSION = 4

# _period_of_day hour boundaries (24h clock, half-open [start, next)).
_MORNING_START_HOUR = 5
_MIDDAY_START_HOUR = 12
_EVENING_START_HOUR = 17
_NIGHT_START_HOUR = 21


def _photo_response(photo: Photo, companion_handles: list[str] | None = None) -> PhotoResponse:
    handle = None
    if photo.tagged_by_user is not None:
        handle = photo.tagged_by_user.handle
    # The upload path passes a Photo constructed in Python, where .diet_tags /
    # .analysis were never eager-loaded (lazy="selectin" only fires at query
    # time); touching them there would trigger implicit async IO
    # (MissingGreenlet). A fresh upload has no tags and no analysis, so
    # treating unloaded as empty is also the correct value.
    unloaded = sa_inspect(photo).unloaded
    diet_tags = [] if "diet_tags" in unloaded else sorted(t.key for t in photo.diet_tags)
    analysis = None if "analysis" in unloaded else photo.analysis
    derived_diet_tags: list[str] = []
    if analysis is not None and analysis.status == "confirmed":
        derived_diet_tags = sorted(compute_signal_from_analyses([analysis]).flags)
    icon_key = None
    if "meal" not in unloaded:
        meal = photo.meal
        icon_key = meal.icon_key if meal is not None else None
    return PhotoResponse(
        id=photo.id,
        entry_id=photo.entry_id,
        meal_id=photo.meal_id,
        filename=photo.filename,
        has_image=bool(photo.filename),
        icon_key=icon_key,
        label=photo.label,
        meal_time=photo.meal_time,
        created_at=photo.created_at,
        hidden_at=photo.hidden_at,
        diet_tags=diet_tags,
        derived_diet_tags=derived_diet_tags,
        source_photo_id=photo.source_photo_id,
        tagged_by_handle=handle,
        tagged_with_handles=companion_handles or [],
    )


async def _build_response(db: AsyncSession, entry: Entry) -> EntryResponse:
    """Construct an ``EntryResponse`` with all computed diet-signal fields."""
    photo_ids = [p.id for p in entry.photos]
    companions = await MealTagCRUD(db).companion_handles_by_photo_ids(photo_ids)
    user_added = parse_diet_risk_csv(entry.diet_risk)
    signal = compute_photo_signal(entry)
    return EntryResponse.model_validate(
        {
            **{c.name: getattr(entry, c.name) for c in entry.__table__.columns},
            "medications": entry.medications_json or [],
            "photos": [_photo_response(p, companions.get(p.id, [])) for p in entry.photos],
            "photo_signal": signal,
            "photo_derived_flags": sorted(signal.flags),
            "user_added_flags": sorted(user_added),
            "effective_flags": sorted(signal.flags | user_added),
        }
    )


def _period_of_day(ts: datetime.datetime) -> str:
    h = ts.hour
    if _MORNING_START_HOUR <= h < _MIDDAY_START_HOUR:
        return "morning"
    if _MIDDAY_START_HOUR <= h < _EVENING_START_HOUR:
        return "midday"
    if _EVENING_START_HOUR <= h < _NIGHT_START_HOUR:
        return "evening"
    return "night"


def _derive_stool_normal(stool_status: Optional[str], current: Optional[bool]) -> Optional[bool]:
    if current is not None:
        return current
    if stool_status == "normal":
        return True
    if stool_status in ("abnormal", "none"):
        return False
    return None


# Unset core scales — a new day (and photo-first skeleton) has no wellbeing
# or gut rating until the user taps a level. Distinct from bloating=0 (None).
NEUTRAL_SKELETON: dict[str, object] = {
    "overall": None,
    "bloating": None,
    "stool_normal": None,
    "joint_pain": 0,
    "neuro": 0,
    "sleep_quality": None,
    "stress": None,
    "diet_risk": "",
    "supplements": "",
    "sick": False,
    "hot_shower": False,
}


async def get_or_create_entry(db: AsyncSession, target_date: datetime.date) -> Entry:
    """Return the entry for ``target_date``, creating a neutral skeleton if absent.

    Used by meal-clone (and any future photo-first flow) to legally satisfy
    Entry's remaining NOT NULL columns without a caller-supplied check-in.
    Core wellbeing/gut scales stay NULL until the user rates them.
    """
    crud = EntryCRUD(db)
    existing = await crud.get_by_date(target_date)
    if existing is not None:
        return existing

    now = datetime.datetime.utcnow()
    entry = Entry(
        user_id=current_user_id(),
        date=target_date,
        schema_version=CURRENT_SCHEMA_VERSION,
        entry_time=now,
        period_of_day=_period_of_day(now),
        symptoms_json={},
        **NEUTRAL_SKELETON,
    )
    return await crud.add_and_flush(entry)


class EntryService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = EntryCRUD(db)

    async def stage_create(self, body: EntryCreate) -> Entry:
        """Validate, build, and add a new Entry to the session -- uncommitted.

        Split out of ``create_entry`` so ``EntryOrchestrator`` can interleave the
        catalog-touch step before the commit, landing entry insert + catalog
        touches in the same transaction (Rule 9.2).
        """
        existing = await self.crud.get_by_date(body.date)
        if existing:
            raise ConflictError(f"Entry for {body.date} already exists")

        data = body.model_dump()
        if data.get("entry_time") is None:
            data["entry_time"] = datetime.datetime.utcnow()
        if data.get("period_of_day") is None:
            data["period_of_day"] = _period_of_day(data["entry_time"])
        if data.get("schema_version") is None:
            data["schema_version"] = CURRENT_SCHEMA_VERSION
        data["stool_normal"] = _derive_stool_normal(
            data.get("stool_status"), data.get("stool_normal")
        )
        data["symptoms_json"] = data.get("symptoms_json") or {}
        data["medications_json"] = data.pop("medications", None) or []

        # stool_completeness (and every other plain EntryCreate field) flows through here
        # via **data -- Entry(**data) is generic over the schema's fields, unlike
        # TreatmentService.create()'s explicit kwarg list, so no per-field wiring is needed.
        entry = Entry(user_id=current_user_id(), **data)
        self.crud.add(entry)
        return entry

    async def stage_update(self, date: datetime.date, body: EntryUpdate) -> Entry:
        """Load and mutate an existing Entry in the session -- uncommitted.

        See ``stage_create`` for why the commit is deferred to the orchestrator.
        """
        entry = await self.crud.get_by_date(date)
        if not entry:
            raise NotFoundError(f"No entry for {date}")

        update_data = body.model_dump(exclude_unset=True)
        # entry_time/period_of_day are server-owned "last edited" stamps, not caller-settable
        # fields, despite EntryUpdate declaring them — every consumer (history page's "Last
        # logged at", insights' correlation-feature exclusion list) treats them as edit-time
        # metadata, never a caller-chosen value. Drop anything the client sent for these
        # before the setattr loop so intent is explicit here rather than a value silently
        # winning then getting clobbered below.
        update_data.pop("entry_time", None)
        update_data.pop("period_of_day", None)
        if "medications" in update_data:
            update_data["medications_json"] = update_data.pop("medications")
        for field, value in update_data.items():
            setattr(entry, field, value)

        entry.stool_normal = _derive_stool_normal(entry.stool_status, entry.stool_normal)

        now = datetime.datetime.utcnow()
        entry.entry_time = now
        entry.period_of_day = _period_of_day(now)
        return entry

    async def list_entries(self, month: Optional[str] = None) -> list[EntryResponse]:
        start: Optional[datetime.date] = None
        end: Optional[datetime.date] = None
        if month:
            year, mon = month.split("-")
            start = datetime.date(int(year), int(mon), 1)
            if int(mon) == 12:
                end = datetime.date(int(year) + 1, 1, 1)
            else:
                end = datetime.date(int(year), int(mon) + 1, 1)
        entries = await self.crud.list(start, end)
        return [await _build_response(self.db, e) for e in entries]

    async def stats(self) -> EntryStatsResponse:
        """Total check-ins, current daily streak, and this week's check-in days.

        Streak = consecutive-calendar-day run walking backwards from the most
        recent entry date, counted only if that date is today or yesterday (a
        user who logged through yesterday hasn't lost their streak yet).
        week_days = Mon..Sun flags for the current local week; future days of
        the week are naturally False.
        Entry dates are stored in the client's local calendar day (see
        formatLocalDate), which may differ by ±1 day from local_today() when
        the device timezone does not match app_timezone.
        Python-side math over just the date column is deliberate — personal-scale
        data, no gaps-and-islands SQL needed.
        """
        dates = await self.crud.list_dates()
        # One `today` for both computations below, so a call spanning local
        # midnight can't report a streak and a week that disagree.
        today = local_today()
        streak = 0
        if dates and (today - dates[0]).days in (-1, 0, 1):
            streak = 1
            for prev, cur in zip(dates, dates[1:]):
                if (prev - cur).days != 1:
                    break
                streak += 1
        monday = today - datetime.timedelta(days=today.weekday())
        date_set = set(dates)
        week_days = [(monday + datetime.timedelta(days=i)) in date_set for i in range(7)]
        return EntryStatsResponse(
            total_checkins=len(dates),
            current_streak_days=streak,
            week_days=week_days,
            week_today_index=today.weekday(),
        )

    async def get_entry(self, date: datetime.date) -> EntryResponse:
        user_id = current_user_id()
        cache_key = entry_key(user_id, date)
        cached = await redis_client.get(cache_key)
        if cached is not None:
            return EntryResponse.model_validate_json(cached)

        entry = await self.crud.get_by_date(date)
        if not entry:
            raise NotFoundError(f"No entry for {date}")
        response = await _build_response(self.db, entry)
        await redis_client.set(
            cache_key,
            response.model_dump_json(),
            settings.cache_ttl_entry_seconds,
        )
        return response

    async def delete_entry(self, date: datetime.date) -> None:
        entry = await self.crud.get_by_date_with_photos(date)
        if not entry:
            raise NotFoundError(f"No entry for {date}")

        photos: list[Photo] = list(entry.photos)
        entry_date = entry.date
        user_id = entry.user_id

        await self.crud.delete_and_commit(entry)
        await invalidate_user_insights_cache(user_id, entry_date)

        for photo in photos:
            # Icon-only library meals have no object-storage file.
            if photo.filename is None:
                continue
            await asyncio.to_thread(delete_photo, photo.filename, user_id=str(photo.user_id))
