from __future__ import annotations

import datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.tracker import Tracker
from app.models.tracker_log import TrackerLog
from app.schemas.tracker import TrackerCreate, TrackerUpdate

# Maps seeded tracker names to the corresponding column on the Entry model.
_SEED_NAME_TO_ENTRY_COL: dict[str, str] = {
    "Alcohol units": "alcohol_units",
    "Caffeine servings": "caffeine_servings",
    "Sick": "sick",
    "Hot shower": "hot_shower",
}

# Fields that callers are not allowed to change via TrackerUpdate.
_IMMUTABLE_FIELDS = {"kind", "is_seed"}


async def list_trackers(db: AsyncSession, include_archived: bool = False) -> list[Tracker]:
    stmt = select(Tracker)
    if not include_archived:
        stmt = stmt.where(Tracker.archived.is_(False))
    stmt = stmt.order_by(Tracker.position.asc(), Tracker.name.asc())
    return list((await db.execute(stmt)).scalars().all())


async def create_tracker(db: AsyncSession, body: TrackerCreate) -> Tracker:
    existing = (
        await db.execute(select(Tracker).where(Tracker.name == body.name))
    ).scalar_one_or_none()
    if existing is not None:
        raise ConflictError(f"Tracker '{body.name}' already exists.")

    # New customs always slot at the end (after seeds + existing customs).
    # Ignore body.position: legacy clients send 0-based custom indices that
    # collide with seed positions 0..3 and interleave on the daily card.
    next_position = (
        await db.execute(
            select(func.coalesce(func.max(Tracker.position), -1)).where(Tracker.archived.is_(False))
        )
    ).scalar() or -1

    tracker = Tracker(
        name=body.name,
        kind=body.kind,
        icon=body.icon,
        unit=body.unit,
        position=next_position + 1,
        archived=False,
        is_seed=False,
    )
    db.add(tracker)
    await db.commit()
    await db.refresh(tracker)
    return tracker


async def update_tracker(db: AsyncSession, tracker_id: int, body: TrackerUpdate) -> Tracker:
    tracker = (
        await db.execute(select(Tracker).where(Tracker.id == tracker_id))
    ).scalar_one_or_none()
    if tracker is None:
        raise NotFoundError(f"Tracker {tracker_id} not found.")

    update_data = body.model_dump(exclude_unset=True)

    for field in _IMMUTABLE_FIELDS:
        if field in update_data:
            raise ValidationError(f"Field '{field}' is immutable and cannot be changed.")

    for field, value in update_data.items():
        setattr(tracker, field, value)

    await db.commit()
    await db.refresh(tracker)
    return tracker


async def reorder_trackers(db: AsyncSession, order: list[int]) -> list[Tracker]:
    # Only non-seed, non-archived trackers are reorderable.
    eligible_ids = set(
        (
            await db.execute(
                select(Tracker.id).where(
                    Tracker.archived.is_(False),
                    Tracker.is_seed.is_(False),
                )
            )
        )
        .scalars()
        .all()
    )
    if set(order) != eligible_ids:
        raise ValidationError(
            "order must contain exactly all active custom tracker ids "
            f"(got {len(order)}, expected {len(eligible_ids)})"
        )

    # Offset past visible seed positions so customs always sort after seeds.
    # Count only active seeds — an archived seed no longer occupies a visible slot.
    seed_count = (
        await db.execute(
            select(func.count())
            .select_from(Tracker)
            .where(
                Tracker.is_seed.is_(True),
                Tracker.archived.is_(False),
            )
        )
    ).scalar() or 0

    for idx, tracker_id in enumerate(order):
        await db.execute(
            update(Tracker).where(Tracker.id == tracker_id).values(position=idx + seed_count)
        )
    await db.commit()
    return await list_trackers(db, include_archived=False)


async def list_tracker_values(db: AsyncSession, date: datetime.date) -> list[TrackerLog]:
    stmt = select(TrackerLog).where(TrackerLog.date == date)
    return list((await db.execute(stmt)).scalars().all())


async def upsert_tracker_value(
    db: AsyncSession, date: datetime.date, tracker_id: int, value: int
) -> TrackerLog:
    tracker = (
        await db.execute(select(Tracker).where(Tracker.id == tracker_id))
    ).scalar_one_or_none()
    if tracker is None:
        raise NotFoundError(f"Tracker {tracker_id} not found.")

    existing = (
        await db.execute(
            select(TrackerLog).where(
                TrackerLog.tracker_id == tracker_id,
                TrackerLog.date == date,
            )
        )
    ).scalar_one_or_none()

    now = datetime.datetime.utcnow()
    if existing is not None:
        existing.value = value
        existing.updated_at = now
        await db.commit()
        await db.refresh(existing)
        log = existing
    else:
        log = TrackerLog(
            tracker_id=tracker_id,
            date=date,
            value=value,
            updated_at=now,
        )
        db.add(log)
        await db.commit()
        await db.refresh(log)

    # If the tracker is a seed, mirror the value back to the matching entry column.
    # This handles Path B (direct PUT to tracker_values for a seeded tracker).
    entry_col = _SEED_NAME_TO_ENTRY_COL.get(tracker.name)
    if tracker.is_seed and entry_col:
        await _mirror_value_to_entry(db, date, entry_col, tracker.kind, value)

    return log


async def _mirror_value_to_entry(
    db: AsyncSession,
    date: datetime.date,
    entry_col: str,
    kind: str,
    value: int,
) -> None:
    """Write a tracker value back to the corresponding Entry column.

    Skips silently when no entry row exists for the date — the entry service
    will call sync_seed_tracker_log_from_entry when the entry is created.
    """
    from app.models.entry import Entry

    entry = (await db.execute(select(Entry).where(Entry.date == date))).scalar_one_or_none()
    if entry is None:
        return

    if kind == "binary":
        setattr(entry, entry_col, bool(value))
    else:
        setattr(entry, entry_col, value)

    await db.commit()


async def sync_seed_tracker_log_from_entry(
    db: AsyncSession,
    entry: object,
) -> None:
    """Upsert tracker_log rows for all seed trackers after an entry is saved.

    Called by the entry service after every create/update (Path A) so that
    tracker_log stays in sync with the legacy entry columns.

    Rules:
    - Counters (alcohol_units, caffeine_servings): skip when value is None or 0.
    - Binaries (sick, hot_shower): skip when value is None or False.
    """
    seed_trackers = list(
        (await db.execute(select(Tracker).where(Tracker.is_seed.is_(True)))).scalars().all()
    )

    now = datetime.datetime.utcnow()
    entry_date = getattr(entry, "date")

    for tracker in seed_trackers:
        entry_col = _SEED_NAME_TO_ENTRY_COL.get(tracker.name)
        if entry_col is None:
            continue

        raw_value = getattr(entry, entry_col, None)

        if raw_value is None:
            continue

        if tracker.kind == "counter" and (not isinstance(raw_value, int) or raw_value == 0):
            continue

        if tracker.kind == "binary" and not raw_value:
            continue

        # Convert bool True → 1 for storage in the integer column
        int_value = 1 if isinstance(raw_value, bool) else int(raw_value)

        existing = (
            await db.execute(
                select(TrackerLog).where(
                    TrackerLog.tracker_id == tracker.id,
                    TrackerLog.date == entry_date,
                )
            )
        ).scalar_one_or_none()

        if existing is not None:
            existing.value = int_value
            existing.updated_at = now
        else:
            db.add(
                TrackerLog(
                    tracker_id=tracker.id,
                    date=entry_date,
                    value=int_value,
                    updated_at=now,
                )
            )

    await db.commit()
