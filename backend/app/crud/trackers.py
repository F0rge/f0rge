from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import BaseCRUD
from app.models.tracker import Tracker
from app.models.tracker_log import TrackerLog
from app.tenant import owned_by_user


class TrackerCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def list(self, include_archived: bool = False) -> list[Tracker]:
        stmt = select(Tracker).where(owned_by_user(Tracker.user_id))
        if not include_archived:
            stmt = stmt.where(Tracker.archived.is_(False))
        stmt = stmt.order_by(Tracker.position.asc(), Tracker.name.asc())
        return list((await self.db.execute(stmt)).scalars().all())

    async def get_by_name(self, name: str) -> Optional[Tracker]:
        stmt = select(Tracker).where(owned_by_user(Tracker.user_id), Tracker.name == name)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_by_id(self, tracker_id: int) -> Optional[Tracker]:
        stmt = select(Tracker).where(owned_by_user(Tracker.user_id), Tracker.id == tracker_id)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def max_active_position(self) -> int:
        stmt = select(func.coalesce(func.max(Tracker.position), -1)).where(
            owned_by_user(Tracker.user_id), Tracker.archived.is_(False)
        )
        return (await self.db.execute(stmt)).scalar() or -1

    async def eligible_reorder_ids(self) -> set[int]:
        stmt = select(Tracker.id).where(
            owned_by_user(Tracker.user_id),
            Tracker.archived.is_(False),
            Tracker.is_seed.is_(False),
        )
        return set((await self.db.execute(stmt)).scalars().all())

    async def count_active_seeds(self) -> int:
        stmt = (
            select(func.count())
            .select_from(Tracker)
            .where(
                owned_by_user(Tracker.user_id),
                Tracker.is_seed.is_(True),
                Tracker.archived.is_(False),
            )
        )
        return (await self.db.execute(stmt)).scalar() or 0

    async def bulk_set_positions(self, order: list[int], seed_count: int) -> None:
        for idx, tracker_id in enumerate(order):
            await self.db.execute(
                update(Tracker).where(Tracker.id == tracker_id).values(position=idx + seed_count)
            )
        await self.db.commit()

    async def list_seed_trackers(self) -> list[Tracker]:
        stmt = select(Tracker).where(owned_by_user(Tracker.user_id), Tracker.is_seed.is_(True))
        return list((await self.db.execute(stmt)).scalars().all())

    async def list_log_values_by_date(self, date: datetime.date) -> list[TrackerLog]:
        stmt = select(TrackerLog).where(owned_by_user(TrackerLog.user_id), TrackerLog.date == date)
        return list((await self.db.execute(stmt)).scalars().all())

    async def get_log(self, tracker_id: int, date: datetime.date) -> Optional[TrackerLog]:
        stmt = select(TrackerLog).where(
            owned_by_user(TrackerLog.user_id),
            TrackerLog.tracker_id == tracker_id,
            TrackerLog.date == date,
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()
