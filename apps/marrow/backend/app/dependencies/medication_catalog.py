from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.medication_catalog import MedicationCatalogService


def get_medication_catalog_service(db: AsyncSession = Depends(get_db)) -> MedicationCatalogService:
    return MedicationCatalogService(db)
