from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.treatments import TreatmentService


def get_treatment_service(db: Session = Depends(get_db)) -> TreatmentService:
    return TreatmentService(db)
