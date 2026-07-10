from __future__ import annotations

import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.entries import EntryCRUD
from app.crud.trackers import TrackerCRUD
from app.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.tracker import Tracker
from app.models.tracker_log import TrackerLog
from app.schemas.tracker import TrackerCreate, TrackerUpdate
from app.tenant import current_user_id

# Maps seeded tracker names to the corresponding column on the Entry model.
_SEED_NAME_TO_ENTRY_COL: dict[str, str] = {
    "Alcohol units": "alcohol_units",
    "Caffeine servings": "caffeine_servings",
    "Sick": "sick",
    "Hot shower": "hot_shower",
}

# Fields that callers are not allowed to change via TrackerUpdate.
_IMMUTABLE_FIELDS = {"kind", "is_seed"}


async def sync_seed_tracker_log_from_entry(
    db: AsyncSession,
    entry: object,
) -> None:
    """Upsert tracker_log rows for all seed trackers after an entry is saved.

    Called by the entry service after every create/update (Path A) so that
    tracker_log stays in sync with the legacy entry columns. Kept as a
    standalone function (not a TrackerService method) — it's a cross-service
    call made on the caller's session, not a request-scoped tracker operation.

    Rules:
    - Counters (alcohol_units, caffeine_servings): skip when value is None or 0.
    - Binaries (sick, hot_shower): skip when value is None or False.
    """
    crud = TrackerCRUD(db)
    seed_trackers = await crud.list_seed_trackers()

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

        existing = await crud.get_log(tracker.id, entry_date)

        if existing is not None:
            existing.value = int_value
            existing.updated_at = now
        else:
            crud.add(
                TrackerLog(
                    user_id=getattr(entry, "user_id", current_user_id()),
                    tracker_id=tracker.id,
                    date=entry_date,
                    value=int_value,
                    updated_at=now,
                )
            )

    await crud.commit()


class TrackerService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = TrackerCRUD(db)

    async def list_trackers(self, include_archived: bool = False) -> list[Tracker]:
        return await self.crud.list(include_archived=include_archived)

    async def create_tracker(self, body: TrackerCreate) -> Tracker:
        existing = await self.crud.get_by_name(body.name)
        if existing is not None:
            raise ConflictError(f"Tracker '{body.name}' already exists.")

        # New customs always slot at the end (after seeds + existing customs).
        # Ignore body.position: legacy clients send 0-based custom indices that
        # collide with seed positions 0..3 and interleave on the daily card.
        next_position = await self.crud.max_active_position()

        tracker = Tracker(
            user_id=current_user_id(),
            name=body.name,
            kind=body.kind,
            icon=body.icon,
            unit=body.unit,
            position=next_position + 1,
            archived=False,
            is_seed=False,
        )
        self.crud.add(tracker)
        return await self.crud.commit_refresh(tracker)

    async def update_tracker(self, tracker_id: int, body: TrackerUpdate) -> Tracker:
        tracker = await self.crud.get_by_id(tracker_id)
        if tracker is None:
            raise NotFoundError(f"Tracker {tracker_id} not found.")

        update_data = body.model_dump(exclude_unset=True)

        for field in _IMMUTABLE_FIELDS:
            if field in update_data:
                raise ValidationError(f"Field '{field}' is immutable and cannot be changed.")

        for field, value in update_data.items():
            setattr(tracker, field, value)

        return await self.crud.commit_refresh(tracker)

    async def reorder_trackers(self, order: list[int]) -> list[Tracker]:
        # Only non-seed, non-archived trackers are reorderable.
        eligible_ids = await self.crud.eligible_reorder_ids()
        if set(order) != eligible_ids:
            raise ValidationError(
                "order must contain exactly all active custom tracker ids "
                f"(got {len(order)}, expected {len(eligible_ids)})"
            )

        # Offset past visible seed positions so customs always sort after seeds.
        # Count only active seeds — an archived seed no longer occupies a visible slot.
        seed_count = await self.crud.count_active_seeds()

        await self.crud.bulk_set_positions(order, seed_count)
        return await self.crud.list(include_archived=False)

    async def list_tracker_values(self, date: datetime.date) -> list[TrackerLog]:
        return await self.crud.list_log_values_by_date(date)

    async def upsert_tracker_value(
        self, date: datetime.date, tracker_id: int, value: int
    ) -> TrackerLog:
        tracker = await self.crud.get_by_id(tracker_id)
        if tracker is None:
            raise NotFoundError(f"Tracker {tracker_id} not found.")

        existing = await self.crud.get_log(tracker_id, date)

        now = datetime.datetime.utcnow()
        if existing is not None:
            existing.value = value
            existing.updated_at = now
            log = await self.crud.commit_refresh(existing)
        else:
            log = TrackerLog(
                user_id=current_user_id(),
                tracker_id=tracker_id,
                date=date,
                value=value,
                updated_at=now,
            )
            self.crud.add(log)
            log = await self.crud.commit_refresh(log)

        # If the tracker is a seed, mirror the value back to the matching entry column.
        # This handles Path B (direct PUT to tracker_values for a seeded tracker).
        entry_col = _SEED_NAME_TO_ENTRY_COL.get(tracker.name)
        if tracker.is_seed and entry_col:
            await self._mirror_value_to_entry(date, entry_col, tracker.kind, value)

        return log

    async def _mirror_value_to_entry(
        self,
        date: datetime.date,
        entry_col: str,
        kind: str,
        value: int,
    ) -> None:
        """Write a tracker value back to the corresponding Entry column.

        Skips silently when no entry row exists for the date — the entry service
        will call sync_seed_tracker_log_from_entry when the entry is created.
        """
        entry = await EntryCRUD(self.db).get_by_date(date)
        if entry is None:
            return

        if kind == "binary":
            setattr(entry, entry_col, bool(value))
        else:
            setattr(entry, entry_col, value)

        await self.crud.commit()
