from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.crud.base import BaseCRUD
from app.models.entry import Entry
from f0rge_db.tenant import owned_by_user


class EntryCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_date(self, date: datetime.date) -> Optional[Entry]:
        stmt = select(Entry).where(owned_by_user(Entry.user_id), Entry.date == date)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_by_date_with_photos(self, date: datetime.date) -> Optional[Entry]:
        stmt = (
            select(Entry)
            .options(selectinload(Entry.photos))
            .where(owned_by_user(Entry.user_id), Entry.date == date)
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def list(
        self,
        start: Optional[datetime.date] = None,
        end: Optional[datetime.date] = None,
    ) -> list[Entry]:
        stmt = select(Entry).where(owned_by_user(Entry.user_id))
        if start is not None:
            stmt = stmt.where(Entry.date >= start)
        if end is not None:
            stmt = stmt.where(Entry.date < end)
        stmt = stmt.order_by(Entry.date.desc())
        return list((await self.db.execute(stmt)).scalars().all())
