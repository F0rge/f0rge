from __future__ import annotations

import datetime
import re
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.treatments import TreatmentCRUD
from app.exceptions import NotFoundError, ValidationError
from app.models.treatment import Treatment
from app.schemas.treatment import TreatmentCreate, TreatmentUpdate
from app.tenant import current_user_id

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class TreatmentService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = TreatmentCRUD(db)

    async def list(self, active_on: Optional[str] = None) -> list[Treatment]:
        active_date = self._parse_active_on(active_on)
        return await self.crud.list(active_date)

    async def get(self, treatment_id: int) -> Treatment:
        treatment = await self.crud.get_by_id(treatment_id)
        if treatment is None:
            raise NotFoundError("Treatment not found.")
        return treatment

    async def create(self, data: TreatmentCreate) -> Treatment:
        self._validate_dates(data.start_date, data.end_date)
        treatment = Treatment(
            user_id=current_user_id(),
            name=data.name,
            normalized_name=self._normalize_name(data.name),
            group_name=data.group_name,
            type=data.type,
            start_date=data.start_date,
            end_date=data.end_date,
            end_reason=data.end_reason,
            end_note=data.end_note,
            dose=data.dose,
            doses_per_day=data.doses_per_day,
            notes=data.notes,
        )
        self.crud.add(treatment)
        return await self.crud.commit_refresh(treatment)

    async def update(self, treatment_id: int, data: TreatmentUpdate) -> Treatment:
        treatment = await self.get(treatment_id)
        patch = data.model_dump(exclude_unset=True)

        new_start = patch.get("start_date", treatment.start_date)
        new_end = patch.get("end_date", treatment.end_date)
        self._validate_dates(new_start, new_end)

        for field, value in patch.items():
            setattr(treatment, field, value)
        if "name" in patch:
            treatment.normalized_name = self._normalize_name(treatment.name)

        return await self.crud.commit_refresh(treatment)

    async def delete(self, treatment_id: int) -> None:
        treatment = await self.get(treatment_id)
        await self.crud.delete_and_commit(treatment)

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
