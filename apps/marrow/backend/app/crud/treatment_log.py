from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import BaseCRUD
from app.models.treatment import Treatment
from app.models.treatment_log import TreatmentLog
from app.tenant import owned_by_user


class TreatmentLogCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get(self, treatment_id: int, date: datetime.date) -> Optional[TreatmentLog]:
        stmt = select(TreatmentLog).where(
            owned_by_user(TreatmentLog.user_id),
            TreatmentLog.treatment_id == treatment_id,
            TreatmentLog.date == date,
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def list_active_treatments(self, on_date: datetime.date) -> list[Treatment]:
        stmt = (
            select(Treatment)
            .where(
                owned_by_user(Treatment.user_id),
                Treatment.start_date <= on_date,
                (Treatment.end_date.is_(None)) | (Treatment.end_date >= on_date),
            )
            .order_by(Treatment.start_date.asc(), Treatment.id.asc())
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def list_dose_tracked_treatments(self, on_date: datetime.date) -> list[Treatment]:
        stmt = select(Treatment).where(
            owned_by_user(Treatment.user_id),
            Treatment.doses_per_day.is_not(None),
            Treatment.start_date <= on_date,
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def list_logs_for_date(
        self, on_date: datetime.date, treatment_ids: list[int]
    ) -> list[TreatmentLog]:
        if not treatment_ids:
            return []
        stmt = select(TreatmentLog).where(
            owned_by_user(TreatmentLog.user_id),
            TreatmentLog.date == on_date,
            TreatmentLog.treatment_id.in_(treatment_ids),
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def list_logs_in_range(
        self, treatment_ids: list[int], start: datetime.date, end: datetime.date
    ) -> list[TreatmentLog]:
        stmt = select(TreatmentLog).where(
            owned_by_user(TreatmentLog.user_id),
            TreatmentLog.treatment_id.in_(treatment_ids),
            TreatmentLog.date >= start,
            TreatmentLog.date <= end,
        )
        return list((await self.db.execute(stmt)).scalars().all())
