from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.tax_invoice import TaxInvoice
from f0rge_db.crud import BaseCRUD


class TaxInvoiceCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_id(self, invoice_id: uuid.UUID) -> Optional[TaxInvoice]:
        return (
            await self.db.execute(
                select(TaxInvoice)
                .options(
                    selectinload(TaxInvoice.customer),
                    selectinload(TaxInvoice.lines),
                )
                .where(TaxInvoice.id == invoice_id)
            )
        ).scalar_one_or_none()

    async def list_for_customer(self, customer_id: uuid.UUID) -> list[TaxInvoice]:
        result = await self.db.execute(
            select(TaxInvoice)
            .options(
                selectinload(TaxInvoice.customer),
                selectinload(TaxInvoice.lines),
            )
            .where(TaxInvoice.customer_id == customer_id)
            .order_by(TaxInvoice.invoice_number)
        )
        return list(result.scalars().all())

    async def list_all(self) -> list[TaxInvoice]:
        result = await self.db.execute(
            select(TaxInvoice)
            .options(
                selectinload(TaxInvoice.customer),
                selectinload(TaxInvoice.lines),
            )
            .order_by(TaxInvoice.invoice_number)
        )
        return list(result.scalars().all())

    async def get_next_invoice_number(self) -> str:
        result = await self.db.execute(
            select(TaxInvoice.invoice_number).order_by(TaxInvoice.invoice_number.desc()).limit(1)
        )
        last = result.scalar_one_or_none()
        if last is None:
            return "INV-0001"
        num = int(last.split("-")[1]) + 1
        return f"INV-{num:04d}"
