from __future__ import annotations

import asyncio
import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.exceptions import ConflictError, NotFoundError
from app.models.entry import Entry
from app.models.photo import Photo
from app.schemas.entry import EntryCreate, EntryResponse, EntryUpdate
from app.schemas.photo import PhotoResponse
from app.services import medication_catalog as medication_catalog_service
from app.services import supplement_catalog as supplement_catalog_service
from app.services import symptom_catalog as symptom_catalog_service
from app.services.diet_flags import compute_photo_signal, parse_diet_risk_csv
from app.services.obsidian import delete_daily_file
from app.services.obsidian_prefetch import render_and_write_daily_file
from app.services.photo_storage import delete_photo
from app.services.trackers import sync_seed_tracker_log_from_entry


def _build_response(entry: Entry) -> EntryResponse:
    """Construct an ``EntryResponse`` with all computed diet-signal fields."""
    user_added = parse_diet_risk_csv(entry.diet_risk)
    signal = compute_photo_signal(entry)
    return EntryResponse.model_validate(
        {
            **{c.name: getattr(entry, c.name) for c in entry.__table__.columns},
            "medications": entry.medications_json or [],
            "photos": [PhotoResponse.model_validate(p, from_attributes=True) for p in entry.photos],
            "photo_signal": signal,
            "photo_derived_flags": sorted(signal.flags),
            "user_added_flags": sorted(user_added),
            "effective_flags": sorted(signal.flags | user_added),
        }
    )


def _period_of_day(ts: datetime.datetime) -> str:
    h = ts.hour
    if 5 <= h < 12:
        return "morning"
    if 12 <= h < 17:
        return "midday"
    if 17 <= h < 21:
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
    create_entry side-effect (catalog touch, tracker sync, vault render): the
    caller owns the transaction and renders the vault once its rows are added.
    """
    existing = (
        await db.execute(select(Entry).where(Entry.date == target_date))
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    now = datetime.datetime.utcnow()
    entry = Entry(
        date=target_date,
        schema_version=2,
        entry_time=now,
        period_of_day=_period_of_day(now),
        overall=2,
        bloating=0,
        stool_normal=True,
        joint_pain=0,
        neuro=0,
        sleep_quality=2,
        stress=1,
        diet_risk="",
        supplements="",
        sick=False,
        hot_shower=False,
        symptoms_json={},
    )
    db.add(entry)
    await db.flush()
    return entry


async def create_entry(db: AsyncSession, body: EntryCreate) -> EntryResponse:
    existing = (await db.execute(select(Entry).where(Entry.date == body.date))).scalar_one_or_none()
    if existing:
        raise ConflictError(f"Entry for {body.date} already exists")

    data = body.model_dump()
    if data.get("entry_time") is None:
        data["entry_time"] = datetime.datetime.utcnow()
    if data.get("period_of_day") is None:
        data["period_of_day"] = _period_of_day(data["entry_time"])
    if data.get("schema_version") is None:
        data["schema_version"] = 3
    data["stool_normal"] = _derive_stool_normal(data.get("stool_status"), data.get("stool_normal"))
    data["symptoms_json"] = data.get("symptoms_json") or {}
    data["medications_json"] = data.pop("medications", None) or []

    entry = Entry(**data)
    db.add(entry)

    supplement_keys = [s.strip() for s in (entry.supplements or "").split(",") if s.strip()]
    await supplement_catalog_service.touch(db, supplement_keys)
    await symptom_catalog_service.touch(db, list((entry.symptoms_json or {}).keys()))
    await medication_catalog_service.touch(
        db, [m["key"] for m in entry.medications_json if m.get("key")]
    )

    await db.commit()
    await db.refresh(entry)

    await sync_seed_tracker_log_from_entry(db, entry)

    await render_and_write_daily_file(db, entry, entry.photos)

    return _build_response(entry)


async def list_entries(db: AsyncSession, month: Optional[str] = None) -> list[EntryResponse]:
    stmt = select(Entry)
    if month:
        year, mon = month.split("-")
        start = datetime.date(int(year), int(mon), 1)
        if int(mon) == 12:
            end = datetime.date(int(year) + 1, 1, 1)
        else:
            end = datetime.date(int(year), int(mon) + 1, 1)
        stmt = stmt.where(Entry.date >= start, Entry.date < end)
    stmt = stmt.order_by(Entry.date.desc())
    entries = list((await db.execute(stmt)).scalars().all())
    return [_build_response(e) for e in entries]


async def get_entry(db: AsyncSession, date: datetime.date) -> EntryResponse:
    entry = (await db.execute(select(Entry).where(Entry.date == date))).scalar_one_or_none()
    if not entry:
        raise NotFoundError(f"No entry for {date}")
    return _build_response(entry)


async def update_entry(db: AsyncSession, date: datetime.date, body: EntryUpdate) -> EntryResponse:
    entry = (await db.execute(select(Entry).where(Entry.date == date))).scalar_one_or_none()
    if not entry:
        raise NotFoundError(f"No entry for {date}")

    update_data = body.model_dump(exclude_unset=True)
    # entry_time/period_of_day are server-owned "last edited" stamps, not caller-settable
    # fields, despite EntryUpdate declaring them — every consumer (history page's "Last
    # logged at", the Obsidian vault's "Logged at" row, insights' correlation-feature
    # exclusion list) treats them as edit-time metadata, never a caller-chosen value. Drop
    # anything the client sent for these before the setattr loop so intent is explicit here
    # rather than a value silently winning then getting clobbered below.
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

    supplement_keys = [s.strip() for s in (entry.supplements or "").split(",") if s.strip()]
    await supplement_catalog_service.touch(db, supplement_keys)
    await symptom_catalog_service.touch(db, list((entry.symptoms_json or {}).keys()))
    await medication_catalog_service.touch(
        db, [m["key"] for m in entry.medications_json if m.get("key")]
    )

    await db.commit()
    await db.refresh(entry)

    await sync_seed_tracker_log_from_entry(db, entry)

    await render_and_write_daily_file(db, entry, entry.photos)

    return _build_response(entry)


async def delete_entry(db: AsyncSession, date: datetime.date) -> None:
    entry = (
        await db.execute(
            select(Entry).options(selectinload(Entry.photos)).where(Entry.date == date)
        )
    ).scalar_one_or_none()
    if not entry:
        raise NotFoundError(f"No entry for {date}")

    photos: list[Photo] = list(entry.photos)
    date_str = entry.date.isoformat()

    await db.delete(entry)
    await db.commit()

    for photo in photos:
        await asyncio.to_thread(delete_photo, photo.filename, settings.vault_path)
    await asyncio.to_thread(delete_daily_file, date_str)
