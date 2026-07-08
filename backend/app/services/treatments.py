from __future__ import annotations

import datetime
import re
from typing import Optional

from sqlalchemy import case, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.exceptions import NotFoundError, ValidationError
from app.models.entry import Entry
from app.models.treatment import Treatment
from app.schemas.treatment import TreatmentCreate, TreatmentUpdate
from app.services.obsidian_prefetch import render_and_write_daily_file
from app.utils.dates import local_today

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class TreatmentService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list(self, active_on: Optional[str] = None) -> list[Treatment]:
        active_date = self._parse_active_on(active_on)
        stmt = select(Treatment)
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

    async def get(self, treatment_id: int) -> Treatment:
        treatment = (
            await self.db.execute(select(Treatment).where(Treatment.id == treatment_id))
        ).scalar_one_or_none()
        if treatment is None:
            raise NotFoundError("Treatment not found.")
        return treatment

    async def create(self, data: TreatmentCreate) -> Treatment:
        self._validate_dates(data.start_date, data.end_date)
        treatment = Treatment(
            name=data.name,
            normalized_name=self._normalize_name(data.name),
            group_name=data.group_name,
            type=data.type,
            start_date=data.start_date,
            end_date=data.end_date,
            dose=data.dose,
            doses_per_day=data.doses_per_day,
            notes=data.notes,
        )
        self.db.add(treatment)
        await self.db.commit()
        await self.db.refresh(treatment)
        await self._rerender_vault_for_range(treatment.start_date, treatment.end_date)
        return treatment

    async def update(self, treatment_id: int, data: TreatmentUpdate) -> Treatment:
        treatment = await self.get(treatment_id)
        old_start, old_end = treatment.start_date, treatment.end_date
        patch = data.model_dump(exclude_unset=True)

        new_start = patch.get("start_date", treatment.start_date)
        new_end = patch.get("end_date", treatment.end_date)
        self._validate_dates(new_start, new_end)

        for field, value in patch.items():
            setattr(treatment, field, value)
        if "name" in patch:
            treatment.normalized_name = self._normalize_name(treatment.name)

        await self.db.commit()
        await self.db.refresh(treatment)

        range_start = min(old_start, treatment.start_date)
        range_end = (
            max(old_end, treatment.end_date)
            if old_end is not None and treatment.end_date is not None
            else None
        )
        await self._rerender_vault_for_range(range_start, range_end)
        return treatment

    async def delete(self, treatment_id: int) -> None:
        treatment = await self.get(treatment_id)
        start_date, end_date = treatment.start_date, treatment.end_date
        await self.db.delete(treatment)
        await self.db.commit()
        await self._rerender_vault_for_range(start_date, end_date)

    @staticmethod
    def _normalize_name(raw: str) -> str:
        key = raw.strip().lower().replace("-", "_").replace(" ", "_")
        return re.sub(r"[^a-z0-9_]", "", key)

    @staticmethod
    def _parse_active_on(value: Optional[str]) -> Optional[datetime.date]:
        if not value:
            return None
        if not _DATE_RE.match(value):
            raise ValidationError("active_on must be YYYY-MM-DD.")
        return datetime.date.fromisoformat(value)

    @staticmethod
    def _validate_dates(
        start_date: datetime.date,
        end_date: Optional[datetime.date],
    ) -> None:
        if end_date is not None and end_date < start_date:
            raise ValidationError("end_date must be on or after start_date.")

    async def _rerender_vault_for_range(
        self,
        start_date: datetime.date,
        end_date: Optional[datetime.date],
    ) -> None:
        upper = end_date if end_date is not None else local_today()
        entries = (
            (
                await self.db.execute(
                    select(Entry)
                    .options(selectinload(Entry.photos))
                    .where(Entry.date >= start_date, Entry.date <= upper)
                )
            )
            .scalars()
            .all()
        )
        for entry in entries:
            await render_and_write_daily_file(self.db, entry, entry.photos)
