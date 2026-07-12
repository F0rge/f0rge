from __future__ import annotations

import asyncio
import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.entries import EntryCRUD
from app.crud.meal_tags import MealTagCRUD
from f0rge_core.exceptions import ConflictError, NotFoundError
from app.models.entry import Entry
from app.models.photo import Photo
from app.schemas.entry import EntryCreate, EntryResponse, EntryUpdate
from app.schemas.photo import PhotoResponse
from app.services.diet_flags import compute_photo_signal, parse_diet_risk_csv
from app.services.photo_storage import delete_photo
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
    return PhotoResponse(
        id=photo.id,
        entry_id=photo.entry_id,
        filename=photo.filename,
        label=photo.label,
        meal_time=photo.meal_time,
        created_at=photo.created_at,
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
            "photos": [
                _photo_response(p, companions.get(p.id, [])) for p in entry.photos
            ],
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


# Neutral scale defaults for a photo-first skeleton entry -- mirrors the
# check-in form's own defaults (mid-scale overall/sleep = 2, stress = 1,
# everything else neutral/off). symptoms_json is deliberately excluded: it's
# a mutable {} and must be constructed fresh per entry, not shared from here.
NEUTRAL_SKELETON: dict[str, object] = {
    "overall": 2,
    "bloating": 0,
    "stool_normal": True,
    "joint_pain": 0,
    "neuro": 0,
    "sleep_quality": 2,
    "stress": 1,
    "diet_risk": "",
    "supplements": "",
    "sick": False,
    "hot_shower": False,
}


async def get_or_create_entry(db: AsyncSession, target_date: datetime.date) -> Entry:
    """Return the entry for ``target_date``, creating a neutral skeleton if absent.

    Used by meal-clone (and any future photo-first flow) to legally satisfy
    Entry's NOT NULL columns without a caller-supplied check-in. The skeleton
    matches the values the frontend already POSTs when a photo is added to an
    untouched day (the check-in form's defaults: mid-scale overall/sleep = 2,
    stress = 1, everything else neutral), so a clone-created day is
    indistinguishable from a photo-first day and the board's pre-fill effect
    reads back valid on-scale values (the wellbeing scales are 1-3, so a 0
    would render as no selection). Flushes only (never commits) and skips every
    create_entry side-effect (catalog touch, tracker sync): the caller owns
    the transaction.
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

    async def get_entry(self, date: datetime.date) -> EntryResponse:
        entry = await self.crud.get_by_date(date)
        if not entry:
            raise NotFoundError(f"No entry for {date}")
        return await _build_response(self.db, entry)

    async def delete_entry(self, date: datetime.date) -> None:
        entry = await self.crud.get_by_date_with_photos(date)
        if not entry:
            raise NotFoundError(f"No entry for {date}")

        photos: list[Photo] = list(entry.photos)

        await self.crud.delete_and_commit(entry)

        for photo in photos:
            await asyncio.to_thread(delete_photo, photo.filename, user_id=str(photo.user_id))
