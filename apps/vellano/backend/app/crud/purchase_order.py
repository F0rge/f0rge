from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.inventory import LocationStock, SkuStock
from app.models.purchase_order import PoLine, PurchaseOrder
from f0rge_db.crud import BaseCRUD


class PurchaseOrderCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_id(self, po_id: uuid.UUID) -> Optional[PurchaseOrder]:
        return (
            await self.db.execute(
                select(PurchaseOrder)
                .options(
                    selectinload(PurchaseOrder.supplier),
                    selectinload(PurchaseOrder.lines).selectinload(PoLine.sku),
                    selectinload(PurchaseOrder.bills),
                )
                .where(PurchaseOrder.id == po_id)
            )
        ).scalar_one_or_none()

    async def list_all(self) -> list[PurchaseOrder]:
        result = await self.db.execute(
            select(PurchaseOrder)
            .options(
                selectinload(PurchaseOrder.supplier),
                selectinload(PurchaseOrder.lines).selectinload(PoLine.sku),
                selectinload(PurchaseOrder.bills),
            )
            .order_by(PurchaseOrder.po_number)
        )
        return list(result.scalars().all())

    async def get_next_po_number(self) -> str:
        result = await self.db.execute(
            select(PurchaseOrder.po_number).order_by(PurchaseOrder.po_number.desc()).limit(1)
        )
        last = result.scalar_one_or_none()
        if last is None:
            return "PO-0001"
        num = int(last.split("-")[1]) + 1
        return f"PO-{num:04d}"


class SkuStockCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_sku_id(self, sku_id: uuid.UUID) -> Optional[SkuStock]:
        return (
            await self.db.execute(select(SkuStock).where(SkuStock.sku_id == sku_id))
        ).scalar_one_or_none()

    async def list_with_movement(self) -> list[SkuStock]:
        result = await self.db.execute(
            select(SkuStock).options(selectinload(SkuStock.sku)).where(SkuStock.on_order > 0)
        )
        return list(result.scalars().all())


class LocationStockCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_sku_and_location(
        self,
        sku_id: uuid.UUID,
        location_id: uuid.UUID,
    ) -> Optional[LocationStock]:
        return (
            await self.db.execute(
                select(LocationStock)
                .options(selectinload(LocationStock.location))
                .where(
                    LocationStock.sku_id == sku_id,
                    LocationStock.location_id == location_id,
                )
            )
        ).scalar_one_or_none()

    async def list_by_location_id(self, location_id: uuid.UUID) -> list[LocationStock]:
        result = await self.db.execute(
            select(LocationStock).where(LocationStock.location_id == location_id)
        )
        return list(result.scalars().all())

    async def list_by_sku_id(self, sku_id: uuid.UUID) -> list[LocationStock]:
        result = await self.db.execute(
            select(LocationStock)
            .options(selectinload(LocationStock.location))
            .where(LocationStock.sku_id == sku_id, LocationStock.on_hand > 0)
        )
        return list(result.scalars().all())

    async def list_with_on_hand(self) -> list[LocationStock]:
        result = await self.db.execute(
            select(LocationStock)
            .options(
                selectinload(LocationStock.sku),
                selectinload(LocationStock.location),
            )
            .where(LocationStock.on_hand > 0)
        )
        return list(result.scalars().all())
