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

    async def get_entry_by_id(self, entry_id: uuid.UUID) -> Optional[JournalEntry]:
        return (
            await self.db.execute(
                select(JournalEntry)
                .options(selectinload(JournalEntry.lines))
                .where(JournalEntry.id == entry_id)
            )
        ).scalar_one_or_none()

    async def add_line(self, line: JournalLine) -> None:
        await self.add_and_flush(line)
