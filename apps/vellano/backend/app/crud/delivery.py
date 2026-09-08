from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.delivery import Delivery, DeliveryLine, DeliveryStatus
from app.models.layby import Layby
from app.models.tax_invoice import TaxInvoice
from f0rge_db.crud import BaseCRUD


class DeliveryCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_id(self, delivery_id: uuid.UUID) -> Optional[Delivery]:
        return (
            await self.db.execute(
                select(Delivery)
                .options(
                    selectinload(Delivery.invoice).selectinload(TaxInvoice.customer),
                    selectinload(Delivery.layby).selectinload(Layby.customer),
                    selectinload(Delivery.location),
                    selectinload(Delivery.lines).selectinload(DeliveryLine.sku),
                )
                .where(Delivery.id == delivery_id)
            )
        ).scalar_one_or_none()

    async def list_all(self) -> list[Delivery]:
        result = await self.db.execute(
            select(Delivery)
            .options(
                selectinload(Delivery.invoice).selectinload(TaxInvoice.customer),
                selectinload(Delivery.layby).selectinload(Layby.customer),
                selectinload(Delivery.location),
                selectinload(Delivery.lines).selectinload(DeliveryLine.sku),
            )
            .order_by(Delivery.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_active_by_invoice_id(self, invoice_id: uuid.UUID) -> Optional[Delivery]:
        return (
            await self.db.execute(
                select(Delivery).where(
                    Delivery.invoice_id == invoice_id,
                    Delivery.status != DeliveryStatus.CANCELLED,
                )
            )
        ).scalar_one_or_none()

    async def get_active_by_layby_id(self, layby_id: uuid.UUID) -> Optional[Delivery]:
        return (
            await self.db.execute(
                select(Delivery).where(
                    Delivery.layby_id == layby_id,
                    Delivery.status != DeliveryStatus.CANCELLED,
                )
            )
        ).scalar_one_or_none()

    async def get_next_delivery_number(self) -> str:
        result = await self.db.execute(
            select(Delivery.delivery_number).order_by(Delivery.delivery_number.desc()).limit(1)
        )
        last = result.scalar_one_or_none()
        if last is None:
            return "DLV-0001"
        num = int(last.split("-")[1]) + 1
        return f"DLV-{num:04d}"
