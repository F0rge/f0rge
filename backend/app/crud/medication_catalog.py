from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CatalogItemCRUD
from app.models.medication_catalog import MedicationCatalogItem


class MedicationCatalogCRUD(CatalogItemCRUD[MedicationCatalogItem]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, MedicationCatalogItem, user_scoped=True)
