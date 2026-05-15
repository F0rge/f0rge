from __future__ import annotations

import datetime
import re
from typing import Optional

from sqlalchemy import case
from sqlalchemy.orm import Session, selectinload

from app.exceptions import NotFoundError, ValidationError
from app.models.entry import Entry
from app.models.treatment import Treatment
from app.schemas.treatment import TreatmentCreate, TreatmentUpdate
from app.services.obsidian import write_daily_file

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class TreatmentService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list(self, active_on: Optional[str] = None) -> list[Treatment]:
        query = self.db.query(Treatment)
        active_date = self._parse_active_on(active_on)
        if active_date is not None:
            query = query.filter(
                Treatment.start_date <= active_date,
                (Treatment.end_date.is_(None)) | (Treatment.end_date >= active_date),
            )
        return query.order_by(
            case((Treatment.end_date.is_(None), 0), else_=1),
            Treatment.start_date.desc(),
        ).all()

    def get(self, treatment_id: int) -> Treatment:
        treatment = (
            self.db.query(Treatment).filter(Treatment.id == treatment_id).first()
        )
        if treatment is None:
            raise NotFoundError("Treatment not found.")
        return treatment

    def create(self, data: TreatmentCreate) -> Treatment:
        self._validate_dates(data.start_date, data.end_date)
        treatment = Treatment(
            name=data.name,
            normalized_name=self._normalize_name(data.name),
            type=data.type,
            start_date=data.start_date,
            end_date=data.end_date,
            dose=data.dose,
            notes=data.notes,
        )
        self.db.add(treatment)
        self.db.commit()
        self.db.refresh(treatment)
        self._rerender_vault_for_range(treatment.start_date, treatment.end_date)
        return treatment

    def update(self, treatment_id: int, data: TreatmentUpdate) -> Treatment:
        treatment = self.get(treatment_id)
        old_start, old_end = treatment.start_date, treatment.end_date
        patch = data.model_dump(exclude_unset=True)

        new_start = patch.get("start_date", treatment.start_date)
        new_end = patch.get("end_date", treatment.end_date)
        self._validate_dates(new_start, new_end)

        for field, value in patch.items():
            setattr(treatment, field, value)
        if "name" in patch:
            treatment.normalized_name = self._normalize_name(treatment.name)

        self.db.commit()
        self.db.refresh(treatment)

        range_start = min(old_start, treatment.start_date)
        range_end = (
            max(old_end, treatment.end_date)
            if old_end is not None and treatment.end_date is not None
            else None
        )
        self._rerender_vault_for_range(range_start, range_end)
        return treatment

    def delete(self, treatment_id: int) -> None:
        treatment = self.get(treatment_id)
        start_date, end_date = treatment.start_date, treatment.end_date
        self.db.delete(treatment)
        self.db.commit()
        self._rerender_vault_for_range(start_date, end_date)

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

    def _rerender_vault_for_range(
        self,
        start_date: datetime.date,
        end_date: Optional[datetime.date],
    ) -> None:
        upper = end_date if end_date is not None else datetime.date.today()
        entries = (
            self.db.query(Entry)
            .options(selectinload(Entry.photos))
            .filter(Entry.date >= start_date, Entry.date <= upper)
            .all()
        )
        for entry in entries:
            write_daily_file(self.db, entry, entry.photos)
