from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.treatments import TreatmentService


def get_treatment_service(db: AsyncSession = Depends(get_db)) -> TreatmentService:
    return TreatmentService(db)
