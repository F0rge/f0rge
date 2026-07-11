from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import BaseCRUD
from app.models.treatment import Treatment
from f0rge_db.tenant import owned_by_user


class InsightsCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def list_treatments_with_start_date(self) -> list[Treatment]:
        stmt = (
            select(Treatment)
            .where(owned_by_user(Treatment.user_id), Treatment.start_date.isnot(None))
            .order_by(Treatment.start_date)
        )
        return list((await self.db.execute(stmt)).scalars().all())
