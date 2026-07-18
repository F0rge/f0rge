"""Dose reminder scheduler (#390).

An in-process asyncio loop (weather_background_loop pattern) that, once a
minute, checks every user's active dose-tracked treatments against their
local-time reminder slots and inserts a ``dose_reminder`` notification per
missed slot. The partial unique index on ``notifications.dedupe_key`` plus
ON CONFLICT DO NOTHING is the multi-instance lock — Fly can run several
machines and exactly one insert wins.
"""

from __future__ import annotations

import asyncio
import datetime
import logging
import uuid
from zoneinfo import ZoneInfo

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.crud.treatment_log import TreatmentLogCRUD
from app.database import async_session_maker
from app.models.notification import Notification
from app.models.user import User
from app.models.user_settings import UserSettings
from f0rge_db.tenant import apply_session_user_id

logger = logging.getLogger(__name__)

SLOT_WINDOW = datetime.timedelta(minutes=15)
_DAY_START = datetime.time(9, 0)
_DAY_SPAN_MINUTES = 12 * 60  # 09:00 → 21:00


def derive_slots(
    doses_per_day: int, reminder_times: list[str] | None = None
) -> list[datetime.time]:
    """Reminder slot times for a treatment, sorted ascending.

    ``reminder_times`` (list of "HH:MM" strings) overrides the derived slots.
    """
    if reminder_times:
        return sorted(datetime.time.fromisoformat(t) for t in reminder_times)
    if doses_per_day == 1:
        return [datetime.time(9, 0)]
    if doses_per_day == 2:
        return [datetime.time(9, 0), datetime.time(21, 0)]
    if doses_per_day == 3:
        return [datetime.time(9, 0), datetime.time(14, 0), datetime.time(21, 0)]
    # >3: evenly spaced between 09:00 and 21:00 inclusive.
    step = _DAY_SPAN_MINUTES / (doses_per_day - 1)
    base = datetime.datetime.combine(datetime.date.min, _DAY_START)
    return [
        (base + datetime.timedelta(minutes=round(i * step))).time() for i in range(doses_per_day)
    ]


async def _tick_user(db: AsyncSession, user_id: uuid.UUID, now: datetime.datetime) -> int:
    """Fire due reminder notifications for one user. Returns rows inserted."""
    await apply_session_user_id(db, user_id)
    tz_name = (
        await db.execute(sa.select(UserSettings.timezone).where(UserSettings.user_id == user_id))
    ).scalar_one_or_none() or settings.app_timezone
    now_local = now.astimezone(ZoneInfo(tz_name))
    today = now_local.date()

    crud = TreatmentLogCRUD(db)
    treatments = [t for t in await crud.list_active_treatments(today) if t.doses_per_day]
    if not treatments:
        return 0
    logs = await crud.list_logs_for_date(today, [t.id for t in treatments])
    taken_by_treatment = {log.treatment_id: log.doses_taken for log in logs}

    fired = 0
    for treatment in treatments:
        taken = taken_by_treatment.get(treatment.id, 0)
        slots = derive_slots(treatment.doses_per_day, treatment.reminder_times)
        for k, slot in enumerate(slots, start=1):
            slot_dt = datetime.datetime.combine(today, slot, tzinfo=now_local.tzinfo)
            if not (slot_dt <= now_local < slot_dt + SLOT_WINDOW):
                continue
            if taken >= k:
                continue
            result = await db.execute(
                pg_insert(Notification)
                .values(
                    user_id=user_id,
                    type="dose_reminder",
                    payload={
                        "treatment_id": str(treatment.id),
                        "treatment_name": treatment.name,
                        "slot": k,
                        "date": today.isoformat(),
                    },
                    dedupe_key=f"dose:{user_id}:{treatment.id}:{today.isoformat()}:{k}",
                )
                .on_conflict_do_nothing()
            )
            fired += result.rowcount
    return fired


async def run_reminder_tick(now: datetime.datetime | None = None) -> int:
    """One scheduler pass over all users. Returns notifications inserted."""
    if now is None:
        now = datetime.datetime.now(datetime.timezone.utc)
    fired = 0
    async with async_session_maker() as db:
        # users is not RLS-user-owned, so listing ids needs no tenant GUC.
        user_ids = (await db.execute(sa.select(User.id))).scalars().all()
        for user_id in user_ids:
            fired += await _tick_user(db, user_id, now)
        await db.commit()
    if fired:
        logger.info("Dose reminder tick inserted %d notification(s)", fired)
    return fired


async def reminder_background_loop() -> None:
    """Run the dose reminder tick every minute in a background task."""
    while True:
        try:
            await run_reminder_tick()
        except Exception:
            logger.exception("Error in reminder background loop")
        await asyncio.sleep(60)
