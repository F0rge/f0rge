from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.crud.base import BaseCRUD
from app.models.lab import Lab
from app.tenant import owned_by_user


class LabCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def list(
        self,
        start_date: Optional[datetime.date] = None,
        end_date: Optional[datetime.date] = None,
        lab_type: Optional[str] = None,
    ) -> list[Lab]:
        stmt = select(Lab).options(selectinload(Lab.markers)).where(owned_by_user(Lab.user_id))
        if start_date is not None:
            stmt = stmt.where(Lab.lab_date >= start_date)
        if end_date is not None:
            stmt = stmt.where(Lab.lab_date <= end_date)
        if lab_type is not None:
            stmt = stmt.where(Lab.type == lab_type)
        stmt = stmt.order_by(Lab.lab_date.desc())
        return list((await self.db.execute(stmt)).scalars().all())

    async def get_by_id(self, lab_id: int) -> Optional[Lab]:
        stmt = (
            select(Lab)
            .options(selectinload(Lab.markers))
            .where(owned_by_user(Lab.user_id), Lab.id == lab_id)
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()
