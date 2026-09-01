from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sku import Sku
from f0rge_db.crud import BaseCRUD


class SkuCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_id(self, sku_id: uuid.UUID) -> Optional[Sku]:
        return (await self.db.execute(select(Sku).where(Sku.id == sku_id))).scalar_one_or_none()

    async def list_all(self) -> list[Sku]:
        result = await self.db.execute(select(Sku).order_by(Sku.our_ref))
        return list(result.scalars().all())

    async def get_by_design_fabric_insensitive(
        self,
        design: str,
        fabric: str,
        exclude_id: Optional[uuid.UUID] = None,
    ) -> Optional[Sku]:
        stmt = select(Sku).where(
            func.lower(Sku.design) == design.lower(),
            func.lower(Sku.fabric) == fabric.lower(),
        )
        if exclude_id is not None:
            stmt = stmt.where(Sku.id != exclude_id)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_by_our_ref(self, our_ref: str) -> Optional[Sku]:
        return (
            await self.db.execute(select(Sku).where(Sku.our_ref == our_ref))
        ).scalar_one_or_none()

    async def get_by_our_barcode(self, our_barcode: str) -> Optional[Sku]:
        return (
            await self.db.execute(select(Sku).where(Sku.our_barcode == our_barcode))
        ).scalar_one_or_none()
