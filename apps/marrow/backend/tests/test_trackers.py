"""Tests for the trackers feature (issue #79).

Covers:
- list_trackers: returns 4 seeded trackers from create_all
- create_tracker: 201, persisted, returned in list
- create_tracker duplicate name: ConflictError raised
- update_tracker: rename, reorder, archive
- update_tracker rejects kind change: ValidationError raised
- PUT value on custom tracker: tracker_log upserted, entry column NOT touched
- PUT value on seeded tracker: tracker_log upserted AND entry column mirrored
- sync_seed_tracker_log_from_entry: creates matching log rows after entry save
- list_tracker_values: returns logs for a date

No DB mocks — all tests use the real testcontainers Postgres via async_db fixture.
"""

from __future__ import annotations

import datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from f0rge_core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.entry import Entry
from app.models.tracker import Tracker
from app.models.tracker_log import TrackerLog
from app.schemas.tracker import TrackerCreate, TrackerUpdate
from app.services.trackers import TrackerService, sync_seed_tracker_log_from_entry

pytestmark = pytest.mark.asyncio

_DATE = datetime.date(2026, 5, 20)
_DATE2 = datetime.date(2026, 5, 21)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _make_entry(
    db: AsyncSession,
    *,
    date: datetime.date = _DATE,
    alcohol_units: int | None = None,
    caffeine_servings: int | None = None,
    sick: bool = False,
    hot_shower: bool = False,
) -> Entry:
    entry = Entry(
        date=date,
        schema_version=3,
        overall=5,
        bloating=0,
        stool_status="normal",
        joint_pain=0,
        neuro=0,
        sleep_quality=7,
        stress=2,
        diet_risk="",
        supplements="",
        sick=sick,
        hot_shower=hot_shower,
        alcohol_units=alcohol_units,
        caffeine_servings=caffeine_servings,
        symptoms_json={},
    )
    db.add(entry)
    await db.flush()
    await db.refresh(entry)
    return entry


async def _get_seeded_tracker(db: AsyncSession, name: str) -> Tracker:
    tracker = (
        await db.execute(select(Tracker).where(Tracker.name == name, Tracker.is_seed.is_(True)))
    ).scalar_one_or_none()
    assert tracker is not None, f"Seeded tracker '{name}' not found — run create_all"
    return tracker


async def _insert_seeds(db: AsyncSession) -> None:
    """Insert the 4 seed trackers that Alembic migration 006 would create.

    create_all does NOT run migrations, so tests that depend on seed presence
    (e.g. reorder position offsets) must call this first.
    """
    for name, kind, icon, unit, position in [
        ("Alcohol units", "counter", "wine", "units", 0),
        ("Caffeine servings", "counter", "coffee", "servings", 1),
        ("Sick", "binary", "thermometer", None, 2),
        ("Hot shower", "binary", "droplets", None, 3),
    ]:
        db.add(
            Tracker(
                name=name,
                kind=kind,
                icon=icon,
                unit=unit,
                position=position,
                archived=False,
                is_seed=True,
            )
        )
    await db.flush()


# ---------------------------------------------------------------------------
# list_trackers
# ---------------------------------------------------------------------------


async def test_list_trackers_returns_seeds(async_db: AsyncSession) -> None:
    """After Base.metadata.create_all the 4 seed trackers are NOT present yet —
    they are inserted by Alembic migration, not by create_all. This test inserts
    them manually to validate the list function."""
    # Insert the 4 seed trackers that migration 006 would normally create.
    for name, kind, icon, unit, position in [
        ("Alcohol units", "counter", "wine", "units", 0),
        ("Caffeine servings", "counter", "coffee", "servings", 1),
        ("Sick", "binary", "thermometer", None, 2),
        ("Hot shower", "binary", "droplets", None, 3),
    ]:
        async_db.add(
            Tracker(
                name=name,
                kind=kind,
                icon=icon,
                unit=unit,
                position=position,
                archived=False,
                is_seed=True,
            )
        )
    await async_db.flush()

    trackers = await TrackerService(async_db).list_trackers()
    names = [t.name for t in trackers]
    assert "Alcohol units" in names
    assert "Caffeine servings" in names
    assert "Sick" in names
    assert "Hot shower" in names


async def test_list_trackers_excludes_archived_by_default(async_db: AsyncSession) -> None:
    async_db.add(
        Tracker(name="archived-tracker", kind="binary", position=99, archived=True, is_seed=False)
    )
    await async_db.flush()

    trackers = await TrackerService(async_db).list_trackers()
    assert not any(t.name == "archived-tracker" for t in trackers)


async def test_list_trackers_includes_archived_when_requested(async_db: AsyncSession) -> None:
    async_db.add(
        Tracker(
            name="archived-tracker-inc",
            kind="binary",
            position=99,
            archived=True,
            is_seed=False,
        )
    )
    await async_db.flush()

    trackers = await TrackerService(async_db).list_trackers(include_archived=True)
    assert any(t.name == "archived-tracker-inc" for t in trackers)


# ---------------------------------------------------------------------------
# create_tracker
# ---------------------------------------------------------------------------


async def test_create_tracker_returns_persisted(async_db: AsyncSession) -> None:
    body = TrackerCreate(name="Mood", kind="binary", icon="smile", unit=None, position=10)
    tracker = await TrackerService(async_db).create_tracker(body)

    assert tracker.id is not None
    assert tracker.name == "Mood"
    assert tracker.kind == "binary"
    assert tracker.icon == "smile"
    assert tracker.is_seed is False
    assert tracker.archived is False

    # Verify it appears in list
    all_trackers = await TrackerService(async_db).list_trackers()
    assert any(t.id == tracker.id for t in all_trackers)


async def test_create_tracker_201_persisted(async_db: AsyncSession) -> None:
    body = TrackerCreate(name="Steps", kind="counter", unit="steps", position=5)
    tracker = await TrackerService(async_db).create_tracker(body)
    assert tracker.id is not None
    assert tracker.unit == "steps"


async def test_create_tracker_duplicate_name_raises_conflict(async_db: AsyncSession) -> None:
    body = TrackerCreate(name="UniqueTracker", kind="binary")
    await TrackerService(async_db).create_tracker(body)

    with pytest.raises(ConflictError):
        await TrackerService(async_db).create_tracker(
            TrackerCreate(name="UniqueTracker", kind="counter")
        )


async def test_create_tracker_slots_at_end_past_seeds(async_db: AsyncSession) -> None:
    """New customs must slot after the 4 seeds (positions 0..3), not collide
    with them. Client-provided body.position is ignored."""
    await _insert_seeds(async_db)
    # Client tries to set position=0 (legacy frontend behavior); server overrides.
    tracker = await TrackerService(async_db).create_tracker(
        TrackerCreate(name="SlotCheck", kind="counter", position=0)
    )
    assert tracker.position == 4  # max(seeds=0..3) + 1

    # A second custom slots after the first.
    second = await TrackerService(async_db).create_tracker(
        TrackerCreate(name="SlotCheck2", kind="counter", position=0)
    )
    assert second.position == 5


# ---------------------------------------------------------------------------
# update_tracker
# ---------------------------------------------------------------------------


async def test_update_tracker_rename(async_db: AsyncSession) -> None:
    tracker = await TrackerService(async_db).create_tracker(
        TrackerCreate(name="OldName", kind="binary")
    )
    updated = await TrackerService(async_db).update_tracker(
        tracker.id, TrackerUpdate(name="NewName")
    )
    assert updated.name == "NewName"


async def test_update_tracker_reorder(async_db: AsyncSession) -> None:
    tracker = await TrackerService(async_db).create_tracker(
        TrackerCreate(name="ReorderMe", kind="binary")
    )
    updated = await TrackerService(async_db).update_tracker(tracker.id, TrackerUpdate(position=42))
    assert updated.position == 42


async def test_update_tracker_archive(async_db: AsyncSession) -> None:
    tracker = await TrackerService(async_db).create_tracker(
        TrackerCreate(name="ArchiveMe", kind="counter")
    )
    updated = await TrackerService(async_db).update_tracker(
        tracker.id, TrackerUpdate(archived=True)
    )
    assert updated.archived is True
    # Should not appear in default list
    active = await TrackerService(async_db).list_trackers()
    assert not any(t.id == tracker.id for t in active)


async def test_update_tracker_rejects_kind_change(async_db: AsyncSession) -> None:
    """TrackerUpdate intentionally excludes 'kind' as a declared field (schema-level guard).
    The service also guards against it as defence-in-depth. We test both:
    1. TrackerUpdate has no 'kind' field, so model_dump never produces it.
    2. The service raises ValidationError when a caller injects it directly."""
    tracker = await TrackerService(async_db).create_tracker(
        TrackerCreate(name="KindLocked", kind="binary")
    )

    # 1. Schema-level: kind must not be a declared field on TrackerUpdate
    assert "kind" not in TrackerUpdate.model_fields

    # 2. Service-level guard: construct a body whose model_dump produces {"kind": "counter"}
    # by subclassing TrackerUpdate with the extra field, passing it explicitly so Pydantic
    # marks it as set (exclude_unset=True will then include it).
    class _TrackerUpdateWithKind(TrackerUpdate):
        kind: str = "counter"

    body_with_kind = _TrackerUpdateWithKind(kind="counter")  # explicitly set → in fields_set
    with pytest.raises(ValidationError):
        await TrackerService(async_db).update_tracker(tracker.id, body_with_kind)  # type: ignore[arg-type]


async def test_update_tracker_not_found(async_db: AsyncSession) -> None:
    with pytest.raises(NotFoundError):
        await TrackerService(async_db).update_tracker(999999, TrackerUpdate(name="Ghost"))


# ---------------------------------------------------------------------------
# reorder_trackers — bulk position update offset past seed range
# ---------------------------------------------------------------------------


async def test_reorder_trackers_persists_order_offset_past_seeds(
    async_db: AsyncSession,
) -> None:
    """Reorder writes positions = idx + seed_count so customs sort after the 4 seeds."""
    await _insert_seeds(async_db)
    a = await TrackerService(async_db).create_tracker(
        TrackerCreate(name="ReorderA", kind="counter")
    )
    b = await TrackerService(async_db).create_tracker(
        TrackerCreate(name="ReorderB", kind="counter")
    )
    c = await TrackerService(async_db).create_tracker(
        TrackerCreate(name="ReorderC", kind="counter")
    )

    result = await TrackerService(async_db).reorder_trackers([c.id, a.id, b.id])

    by_id = {t.id: t.position for t in result}
    # 4 seeded trackers occupy positions 0..3, customs get 4, 5, 6 in given order.
    assert by_id[c.id] == 4
    assert by_id[a.id] == 5
    assert by_id[b.id] == 6

    # list_trackers sorts by position then name → seeds first, then customs in given order.
    active = await TrackerService(async_db).list_trackers(include_archived=False)
    custom_names_in_order = [t.name for t in active if not t.is_seed]
    assert custom_names_in_order == ["ReorderC", "ReorderA", "ReorderB"]


async def test_reorder_trackers_keeps_seeds_first_on_daily_card(
    async_db: AsyncSession,
) -> None:
    """After reorder, list_trackers returns seeds at positions 0..3 then customs at 4+."""
    await _insert_seeds(async_db)
    a = await TrackerService(async_db).create_tracker(
        TrackerCreate(name="ReorderA", kind="counter")
    )
    b = await TrackerService(async_db).create_tracker(
        TrackerCreate(name="ReorderB", kind="counter")
    )
    await TrackerService(async_db).reorder_trackers([b.id, a.id])

    active = await TrackerService(async_db).list_trackers(include_archived=False)
    # First 4 are seeds (positions 0..3), then customs in the chosen order.
    assert [t.is_seed for t in active] == [True, True, True, True, False, False]
    assert [t.name for t in active[-2:]] == ["ReorderB", "ReorderA"]


async def test_reorder_trackers_rejects_unknown_id(async_db: AsyncSession) -> None:
    a = await TrackerService(async_db).create_tracker(
        TrackerCreate(name="ReorderKnown", kind="counter")
    )
    with pytest.raises(ValidationError):
        await TrackerService(async_db).reorder_trackers([a.id, 999999])


async def test_reorder_trackers_rejects_seeded_id(async_db: AsyncSession) -> None:
    """Seeded trackers are not reorderable through this endpoint."""
    await _insert_seeds(async_db)
    seed = await _get_seeded_tracker(async_db, "Alcohol units")
    custom = await TrackerService(async_db).create_tracker(
        TrackerCreate(name="ReorderCustom", kind="counter")
    )
    with pytest.raises(ValidationError):
        await TrackerService(async_db).reorder_trackers([custom.id, seed.id])


async def test_reorder_trackers_rejects_archived_id(async_db: AsyncSession) -> None:
    tracker = await TrackerService(async_db).create_tracker(
        TrackerCreate(name="ReorderArchived", kind="counter")
    )
    await TrackerService(async_db).update_tracker(tracker.id, TrackerUpdate(archived=True))
    with pytest.raises(ValidationError):
        await TrackerService(async_db).reorder_trackers([tracker.id])


async def test_reorder_trackers_rejects_partial_order(async_db: AsyncSession) -> None:
    """Caller must include every eligible custom tracker in `order`; partial lists
    would leave the omitted trackers with stale positions that collide with the
    newly assigned ones."""
    a = await TrackerService(async_db).create_tracker(
        TrackerCreate(name="PartialA", kind="counter")
    )
    b = await TrackerService(async_db).create_tracker(
        TrackerCreate(name="PartialB", kind="counter")
    )
    with pytest.raises(ValidationError, match="exactly all"):
        await TrackerService(async_db).reorder_trackers([a.id])  # missing b.id
    # Reference b so the test doesn't trip "unused variable" lint.
    assert b.id != a.id


# ---------------------------------------------------------------------------
# OrderRequest schema validation
# ---------------------------------------------------------------------------


async def test_order_request_rejects_duplicates() -> None:
    from app.schemas.tracker import OrderRequest
    from pydantic import ValidationError as PydanticValidationError

    with pytest.raises(PydanticValidationError, match="duplicate"):
        OrderRequest(order=[1, 2, 1])


# ---------------------------------------------------------------------------
# upsert_tracker_value — custom tracker (no entry mirror)
# ---------------------------------------------------------------------------


async def test_upsert_custom_tracker_value_no_entry_mirror(async_db: AsyncSession) -> None:
    tracker = await TrackerService(async_db).create_tracker(
        TrackerCreate(name="CustomCounter", kind="counter", unit="reps")
    )
    log = await TrackerService(async_db).upsert_tracker_value(_DATE, tracker.id, 5)

    assert log.tracker_id == tracker.id
    assert log.date == _DATE
    assert log.value == 5

    # No entry row should have been created as a side effect
    entry = (await async_db.execute(select(Entry).where(Entry.date == _DATE))).scalar_one_or_none()
    assert entry is None


async def test_upsert_custom_tracker_value_idempotent(async_db: AsyncSession) -> None:
    tracker = await TrackerService(async_db).create_tracker(
        TrackerCreate(name="IdempotentTracker", kind="counter")
    )
    await TrackerService(async_db).upsert_tracker_value(_DATE2, tracker.id, 3)
    log = await TrackerService(async_db).upsert_tracker_value(_DATE2, tracker.id, 7)

    assert log.value == 7

    # Only one log row should exist
    all_logs = (
        (
            await async_db.execute(
                select(TrackerLog).where(
                    TrackerLog.tracker_id == tracker.id,
                    TrackerLog.date == _DATE2,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(all_logs) == 1


# ---------------------------------------------------------------------------
# upsert_tracker_value — seeded tracker (entry column mirror)
# ---------------------------------------------------------------------------


async def _insert_seed_tracker(
    db: AsyncSession, name: str, kind: str, icon: str, unit: str | None, position: int
) -> Tracker:
    """Insert a seed tracker (simulating what migration 006 does)."""
    existing = (
        await db.execute(select(Tracker).where(Tracker.name == name, Tracker.is_seed.is_(True)))
    ).scalar_one_or_none()
    if existing:
        return existing
    t = Tracker(
        name=name, kind=kind, icon=icon, unit=unit, position=position, archived=False, is_seed=True
    )
    db.add(t)
    await db.flush()
    await db.refresh(t)
    return t


async def test_upsert_seeded_tracker_mirrors_to_entry(async_db: AsyncSession) -> None:
    alcohol_tracker = await _insert_seed_tracker(
        async_db, "Alcohol units", "counter", "wine", "units", 0
    )
    entry = await _make_entry(async_db, date=_DATE, alcohol_units=0)

    log = await TrackerService(async_db).upsert_tracker_value(_DATE, alcohol_tracker.id, 3)
    assert log.value == 3

    # Entry column should be mirrored
    await async_db.refresh(entry)
    assert entry.alcohol_units == 3


async def test_upsert_seeded_tracker_binary_mirrors_to_entry(async_db: AsyncSession) -> None:
    sick_tracker = await _insert_seed_tracker(async_db, "Sick", "binary", "thermometer", None, 2)
    entry = await _make_entry(async_db, date=datetime.date(2026, 5, 22), sick=False)

    log = await TrackerService(async_db).upsert_tracker_value(
        datetime.date(2026, 5, 22), sick_tracker.id, 1
    )
    assert log.value == 1

    await async_db.refresh(entry)
    assert entry.sick is True


async def test_upsert_seeded_tracker_no_entry_skips_mirror(async_db: AsyncSession) -> None:
    """When no entry exists for the date, upsert still succeeds (no 500)."""
    caffeine_tracker = await _insert_seed_tracker(
        async_db, "Caffeine servings", "counter", "coffee", "servings", 1
    )
    no_entry_date = datetime.date(2026, 1, 1)

    log = await TrackerService(async_db).upsert_tracker_value(no_entry_date, caffeine_tracker.id, 2)
    assert log.value == 2

    # No entry should have been created
    entry = (
        await async_db.execute(select(Entry).where(Entry.date == no_entry_date))
    ).scalar_one_or_none()
    assert entry is None


# ---------------------------------------------------------------------------
# sync_seed_tracker_log_from_entry
# ---------------------------------------------------------------------------


async def test_sync_creates_tracker_log_from_entry(async_db: AsyncSession) -> None:
    alcohol_tracker = await _insert_seed_tracker(
        async_db, "Alcohol units", "counter", "wine", "units", 0
    )
    caffeine_tracker = await _insert_seed_tracker(
        async_db, "Caffeine servings", "counter", "coffee", "servings", 1
    )
    sick_tracker = await _insert_seed_tracker(async_db, "Sick", "binary", "thermometer", None, 2)
    hot_shower_tracker = await _insert_seed_tracker(
        async_db, "Hot shower", "binary", "droplets", None, 3
    )

    entry_date = datetime.date(2026, 5, 10)
    entry = await _make_entry(
        async_db,
        date=entry_date,
        alcohol_units=2,
        sick=True,
    )

    await sync_seed_tracker_log_from_entry(async_db, entry)

    logs = await TrackerService(async_db).list_tracker_values(entry_date)
    log_by_tracker = {log.tracker_id: log for log in logs}

    # alcohol_units=2 → logged
    assert alcohol_tracker.id in log_by_tracker
    assert log_by_tracker[alcohol_tracker.id].value == 2

    # sick=True → logged as 1
    assert sick_tracker.id in log_by_tracker
    assert log_by_tracker[sick_tracker.id].value == 1

    # caffeine_servings=None → not logged
    assert caffeine_tracker.id not in log_by_tracker

    # hot_shower=False → not logged
    assert hot_shower_tracker.id not in log_by_tracker


async def test_sync_skips_zero_counters(async_db: AsyncSession) -> None:
    alcohol_tracker = await _insert_seed_tracker(
        async_db, "Alcohol units", "counter", "wine", "units", 0
    )
    entry_date = datetime.date(2026, 5, 11)
    entry = await _make_entry(async_db, date=entry_date, alcohol_units=0)

    await sync_seed_tracker_log_from_entry(async_db, entry)

    logs = await TrackerService(async_db).list_tracker_values(entry_date)
    assert not any(log.tracker_id == alcohol_tracker.id for log in logs)


async def test_sync_is_idempotent(async_db: AsyncSession) -> None:
    alcohol_tracker = await _insert_seed_tracker(
        async_db, "Alcohol units", "counter", "wine", "units", 0
    )
    entry_date = datetime.date(2026, 5, 12)
    entry = await _make_entry(async_db, date=entry_date, alcohol_units=3)

    await sync_seed_tracker_log_from_entry(async_db, entry)
    await sync_seed_tracker_log_from_entry(async_db, entry)

    logs = await TrackerService(async_db).list_tracker_values(entry_date)
    alcohol_logs = [log for log in logs if log.tracker_id == alcohol_tracker.id]
    assert len(alcohol_logs) == 1
    assert alcohol_logs[0].value == 3


# ---------------------------------------------------------------------------
# list_tracker_values
# ---------------------------------------------------------------------------


async def test_list_tracker_values_returns_logs_for_date(async_db: AsyncSession) -> None:
    tracker = await TrackerService(async_db).create_tracker(
        TrackerCreate(name="ListValuesTracker", kind="counter")
    )
    log_date = datetime.date(2026, 5, 15)
    other_date = datetime.date(2026, 5, 16)

    await TrackerService(async_db).upsert_tracker_value(log_date, tracker.id, 10)
    await TrackerService(async_db).upsert_tracker_value(other_date, tracker.id, 20)

    logs = await TrackerService(async_db).list_tracker_values(log_date)
    assert any(log.tracker_id == tracker.id and log.value == 10 for log in logs)
    assert not any(log.date == other_date for log in logs)


async def test_list_tracker_values_empty_for_date_with_no_logs(async_db: AsyncSession) -> None:
    logs = await TrackerService(async_db).list_tracker_values(datetime.date(2000, 1, 1))
    assert logs == []
