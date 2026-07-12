from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import case, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import BaseCRUD
from app.models.treatment import Treatment
from f0rge_db.tenant import owned_by_user


class TreatmentCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def list(self, active_date: Optional[datetime.date] = None) -> list[Treatment]:
        stmt = select(Treatment).where(owned_by_user(Treatment.user_id))
        if active_date is not None:
            stmt = stmt.where(
                Treatment.start_date <= active_date,
                (Treatment.end_date.is_(None)) | (Treatment.end_date >= active_date),
            )
        stmt = stmt.order_by(
            case((Treatment.end_date.is_(None), 0), else_=1),
            Treatment.start_date.desc(),
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def get_by_id(self, treatment_id: int) -> Optional[Treatment]:
        stmt = select(Treatment).where(
            owned_by_user(Treatment.user_id), Treatment.id == treatment_id
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()
