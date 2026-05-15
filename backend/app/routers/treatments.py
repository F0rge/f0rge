from __future__ import annotations

import datetime
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.middleware.auth import get_current_session
from app.models.entry import Entry
from app.models.treatment import Treatment
from app.schemas.treatment import TreatmentCreate, TreatmentResponse, TreatmentUpdate
from app.services.obsidian import write_daily_file

router = APIRouter(
    prefix="/api/v1/treatments",
    tags=["treatments"],
    dependencies=[Depends(get_current_session)],
)


def _normalize_name(raw: str) -> str:
    key = raw.strip().lower().replace("-", "_").replace(" ", "_")
    return re.sub(r"[^a-z0-9_]", "", key)


def _rerender_vault_for_range(
    db: Session,
    start_date,
    end_date,
) -> None:
    if end_date is None:
        end_date = datetime.date.today()
    entries = (
        db.query(Entry)
        .options(selectinload(Entry.photos))
        .filter(Entry.date >= start_date, Entry.date <= end_date)
        .all()
    )
    for entry in entries:
        write_daily_file(db, entry, entry.photos)


@router.get("", response_model=list[TreatmentResponse])
def list_treatments(
    active_on: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    db: Session = Depends(get_db),
):
    query = db.query(Treatment)

    if active_on:
        d = datetime.date.fromisoformat(active_on)
        query = query.filter(
            Treatment.start_date <= d,
            (Treatment.end_date.is_(None)) | (Treatment.end_date >= d),
        )

    return query.order_by(
        case((Treatment.end_date.is_(None), 0), else_=1),
        Treatment.start_date.desc(),
    ).all()


@router.get("/{treatment_id}", response_model=TreatmentResponse)
def get_treatment(treatment_id: int, db: Session = Depends(get_db)):
    treatment = db.query(Treatment).filter(Treatment.id == treatment_id).first()
    if not treatment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Treatment not found.",
        )
    return treatment


@router.post(
    "",
    response_model=TreatmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_treatment(body: TreatmentCreate, db: Session = Depends(get_db)):
    if body.end_date is not None and body.end_date < body.start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="end_date must be on or after start_date.",
        )

    treatment = Treatment(
        name=body.name,
        normalized_name=_normalize_name(body.name),
        type=body.type,
        start_date=body.start_date,
        end_date=body.end_date,
        dose=body.dose,
        notes=body.notes,
    )
    db.add(treatment)
    db.commit()
    db.refresh(treatment)

    _rerender_vault_for_range(db, treatment.start_date, treatment.end_date)

    return treatment


@router.put("/{treatment_id}", response_model=TreatmentResponse)
def update_treatment(
    treatment_id: int,
    body: TreatmentUpdate,
    db: Session = Depends(get_db),
):
    treatment = db.query(Treatment).filter(Treatment.id == treatment_id).first()
    if not treatment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Treatment not found.",
        )

    old_start = treatment.start_date
    old_end = treatment.end_date

    data = body.model_dump(exclude_unset=True)

    new_start = data.get("start_date", treatment.start_date)
    new_end = data.get("end_date", treatment.end_date)
    if new_end is not None and new_end < new_start:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="end_date must be on or after start_date.",
        )

    for field, value in data.items():
        setattr(treatment, field, value)

    if data.get("name") is not None:
        treatment.normalized_name = _normalize_name(treatment.name)

    db.commit()
    db.refresh(treatment)

    range_start = min(old_start, treatment.start_date)
    range_end = None
    if old_end is not None and treatment.end_date is not None:
        range_end = max(old_end, treatment.end_date)

    _rerender_vault_for_range(db, range_start, range_end)

    return treatment


@router.delete("/{treatment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_treatment(treatment_id: int, db: Session = Depends(get_db)):
    treatment = db.query(Treatment).filter(Treatment.id == treatment_id).first()
    if not treatment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Treatment not found.",
        )

    start_date = treatment.start_date
    end_date = treatment.end_date

    db.delete(treatment)
    db.commit()

    _rerender_vault_for_range(db, start_date, end_date)
