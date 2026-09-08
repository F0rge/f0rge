from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.proforma import Proforma
from f0rge_db.crud import BaseCRUD


class ProformaCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_id(self, proforma_id: uuid.UUID) -> Optional[Proforma]:
        return (
            await self.db.execute(
                select(Proforma)
                .options(selectinload(Proforma.supplier))
                .where(Proforma.id == proforma_id)
            )
        ).scalar_one_or_none()

    async def list_all(self) -> list[Proforma]:
        result = await self.db.execute(
            select(Proforma)
            .options(selectinload(Proforma.supplier))
            .order_by(Proforma.invoice_date.desc(), Proforma.invoice_number)
        )
        return list(result.scalars().all())
