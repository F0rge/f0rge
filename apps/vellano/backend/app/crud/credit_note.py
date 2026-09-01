from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.credit_note import CreditNote
from app.models.tax_invoice import TaxInvoice
from f0rge_db.crud import BaseCRUD


class CreditNoteCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_id(self, credit_note_id: uuid.UUID) -> Optional[CreditNote]:
        return (
            await self.db.execute(
                select(CreditNote)
                .options(selectinload(CreditNote.invoice).selectinload(TaxInvoice.customer))
                .where(CreditNote.id == credit_note_id)
            )
        ).scalar_one_or_none()

    async def get_by_invoice_id(self, invoice_id: uuid.UUID) -> Optional[CreditNote]:
        return (
            await self.db.execute(select(CreditNote).where(CreditNote.invoice_id == invoice_id))
        ).scalar_one_or_none()

    async def list_all(self) -> list[CreditNote]:
        result = await self.db.execute(
            select(CreditNote)
            .options(selectinload(CreditNote.invoice))
            .order_by(CreditNote.credit_note_number)
        )
        return list(result.scalars().all())

    async def get_next_credit_note_number(self) -> str:
        result = await self.db.execute(
            select(CreditNote.credit_note_number)
            .order_by(CreditNote.credit_note_number.desc())
            .limit(1)
        )
        last = result.scalar_one_or_none()
        if last is None:
            return "CN-0001"
        num = int(last.split("-")[1]) + 1
        return f"CN-{num:04d}"
