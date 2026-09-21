from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.repeating_invoice import RepeatingInvoice
from f0rge_db.crud import BaseCRUD


class RepeatingInvoiceCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_id(self, schedule_id: uuid.UUID) -> Optional[RepeatingInvoice]:
        return (
            await self.db.execute(
                select(RepeatingInvoice)
                .options(selectinload(RepeatingInvoice.lines))
                .where(RepeatingInvoice.id == schedule_id)
            )
        ).scalar_one_or_none()

    async def list_all(self) -> list[RepeatingInvoice]:
        result = await self.db.execute(
            select(RepeatingInvoice)
            .options(selectinload(RepeatingInvoice.lines))
            .order_by(RepeatingInvoice.next_date, RepeatingInvoice.created_at)
        )
        return list(result.scalars().all())
