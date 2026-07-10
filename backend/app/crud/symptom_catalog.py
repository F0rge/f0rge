from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CatalogItemCRUD
from app.models.symptom_catalog import SymptomCatalogItem
from app.tenant import owned_by_user


class SymptomCatalogCRUD(CatalogItemCRUD[SymptomCatalogItem]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, SymptomCatalogItem, user_scoped=True)

    async def eligible_keys(self) -> set[str]:
        stmt = self._scope(
            select(SymptomCatalogItem.key).where(SymptomCatalogItem.archived.is_(False))
        )
        return set((await self.db.execute(stmt)).scalars().all())

    async def bulk_set_sort_order(self, order: list[str]) -> None:
        for idx, key in enumerate(order):
            await self.db.execute(
                update(SymptomCatalogItem)
                .where(
                    owned_by_user(SymptomCatalogItem.user_id),
                    SymptomCatalogItem.key == key,
                )
                .values(sort_order=idx)
            )
        await self.save()
