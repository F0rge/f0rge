from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.treatment_extraction import TreatmentExtractionService
from app.services.treatment_extraction_orchestrator import TreatmentExtractionOrchestrator
from app.services.treatments import TreatmentService


def get_treatment_service(db: AsyncSession = Depends(get_db)) -> TreatmentService:
    return TreatmentService(db)


def get_treatment_extraction_service(
    db: AsyncSession = Depends(get_db),
) -> TreatmentExtractionService:
    return TreatmentExtractionService(db)


def get_treatment_extraction_orchestrator(
    extraction_service: TreatmentExtractionService = Depends(get_treatment_extraction_service),
) -> TreatmentExtractionOrchestrator:
    return TreatmentExtractionOrchestrator(extraction_service)
