from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CatalogItemCRUD
from app.models.diet_tag_catalog import DietTagCatalogItem


class DietTagCatalogCRUD(CatalogItemCRUD[DietTagCatalogItem]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, DietTagCatalogItem, user_scoped=False)
