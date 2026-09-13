from __future__ import annotations

import datetime
import uuid
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.journal import JournalEntry, JournalLine, JournalStatus
from f0rge_db.crud import BaseCRUD


class JournalCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    def _with_lines(self):
        return select(JournalEntry).options(
            selectinload(JournalEntry.lines).selectinload(JournalLine.account)
        )

    async def get_entry_by_id(self, entry_id: uuid.UUID) -> Optional[JournalEntry]:
        return (
            await self.db.execute(self._with_lines().where(JournalEntry.id == entry_id))
        ).scalar_one_or_none()

    async def list_all(self) -> list[JournalEntry]:
        result = await self.db.execute(
            self._with_lines().order_by(JournalEntry.created_at.desc(), JournalEntry.id.desc())
        )
        return list(result.scalars().all())

    async def list_page(
        self,
        *,
        limit: int,
        offset: int,
        q: Optional[str] = None,
    ) -> tuple[list[JournalEntry], int]:
        filters = []
        if q:
            pattern = f"%{q}%"
            filters.append(
                or_(
                    JournalEntry.journal_number.ilike(pattern),
                    JournalEntry.memo.ilike(pattern),
                )
            )
        count_stmt = select(func.count(JournalEntry.id))
        if filters:
            count_stmt = count_stmt.where(*filters)
        total = await self.db.scalar(count_stmt) or 0

        stmt = select(JournalEntry).options(selectinload(JournalEntry.lines))
        if filters:
            stmt = stmt.where(*filters)
        stmt = stmt.order_by(
            JournalEntry.entry_date.desc(),
            JournalEntry.journal_number.desc().nulls_last(),
        ).limit(limit).offset(offset)
        result = await self.db.execute(stmt)
        return list(result.scalars().unique().all()), total

    async def get_next_journal_number(self) -> str:
        result = await self.db.execute(
            select(JournalEntry.journal_number)
            .where(JournalEntry.journal_number.is_not(None))
            .order_by(JournalEntry.journal_number.desc())
            .limit(1)
        )
        last = result.scalar_one_or_none()
        if last is None:
            return "JE-0001"
        num = int(last.split("-")[1]) + 1
        return f"JE-{num:04d}"

    async def add_line(self, line: JournalLine) -> None:
        await self.add_and_flush(line)

    async def get_posted_for_source_month(
        self, source: str, entry_date: datetime.date
    ) -> Optional[JournalEntry]:
        start = entry_date.replace(day=1)
        if start.month == 12:
            end = datetime.date(start.year + 1, 1, 1)
        else:
            end = datetime.date(start.year, start.month + 1, 1)
        result = await self.db.execute(
            select(JournalEntry)
            .where(
                JournalEntry.source == source,
                JournalEntry.status == JournalStatus.POSTED,
                JournalEntry.entry_date >= start,
                JournalEntry.entry_date < end,
            )
            .limit(1)
        )
        return result.scalar_one_or_none()
