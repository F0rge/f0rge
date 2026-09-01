from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.journal import JournalEntry, JournalLine
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
