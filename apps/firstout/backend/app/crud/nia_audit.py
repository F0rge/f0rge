from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.nia import NiaAuditEvent
from f0rge_db.crud import BaseCRUD


class NiaAuditCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def list_for_thread(self, thread_id: uuid.UUID) -> list[NiaAuditEvent]:
        stmt = (
            select(NiaAuditEvent)
            .where(NiaAuditEvent.thread_id == thread_id)
            .order_by(NiaAuditEvent.created_at.asc(), NiaAuditEvent.id.asc())
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def count_all(self) -> int:
        result = await self.db.execute(select(func.count()).select_from(NiaAuditEvent))
        return int(result.scalar_one())

    async def list_newest(self, limit: int) -> list[NiaAuditEvent]:
        stmt = (
            select(NiaAuditEvent)
            .options(selectinload(NiaAuditEvent.user))
            .order_by(NiaAuditEvent.created_at.desc(), NiaAuditEvent.id.desc())
            .limit(limit)
        )
        return list((await self.db.execute(stmt)).scalars().all())
