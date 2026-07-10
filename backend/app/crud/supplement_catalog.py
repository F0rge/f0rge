from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CatalogItemCRUD
from app.models.supplement_catalog import SupplementCatalogItem


class SupplementCatalogCRUD(CatalogItemCRUD[SupplementCatalogItem]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, SupplementCatalogItem, user_scoped=True)
