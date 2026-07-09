from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.symptom_catalog import SymptomCatalogService


def get_symptom_catalog_service(db: AsyncSession = Depends(get_db)) -> SymptomCatalogService:
    return SymptomCatalogService(db)
