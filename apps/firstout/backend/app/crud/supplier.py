from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.supplier import Supplier
from app.models.sku_supplier_price import SkuSupplierPrice
from f0rge_db.organisation import tenant_id_ctx
from f0rge_db.crud import BaseCRUD


class SupplierCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_id(self, supplier_id: uuid.UUID) -> Optional[Supplier]:
        return (
            await self.db.execute(select(Supplier).where(Supplier.id == supplier_id))
        ).scalar_one_or_none()

    async def list_all(self) -> list[Supplier]:
        result = await self.db.execute(select(Supplier).order_by(Supplier.name))
        return list(result.scalars().all())

    async def get_by_name_insensitive(self, name: str) -> Optional[Supplier]:
        return (
            await self.db.execute(select(Supplier).where(func.lower(Supplier.name) == name.lower()))
        ).scalar_one_or_none()

    async def names_by_ids(self, supplier_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
        if not supplier_ids:
            return {}
        result = await self.db.execute(
            select(Supplier.id, Supplier.name).where(Supplier.id.in_(supplier_ids))
        )
        return {row[0]: row[1] for row in result.all()}

    async def supplier_code_for_sku(
        self, supplier_id: uuid.UUID, sku_id: uuid.UUID
    ) -> Optional[str]:
        return await self.db.scalar(
            select(SkuSupplierPrice.supplier_sku).where(
                SkuSupplierPrice.team_id == tenant_id_ctx.get(),
                SkuSupplierPrice.supplier_id == supplier_id,
                SkuSupplierPrice.sku_id == sku_id,
            )
        )
