from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.treatment_log import TreatmentLogService


def get_treatment_log_service(db: AsyncSession = Depends(get_db)) -> TreatmentLogService:
    return TreatmentLogService(db)
