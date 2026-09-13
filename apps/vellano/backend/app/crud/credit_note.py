from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, aliased

from app.models.credit_note import CreditNote
from app.models.customer import Customer
from app.models.tax_invoice import TaxInvoice
from f0rge_db.crud import BaseCRUD


class CreditNoteCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_id(self, credit_note_id: uuid.UUID) -> Optional[CreditNote]:
        return (
            await self.db.execute(
                select(CreditNote)
                .options(
                    selectinload(CreditNote.invoice).selectinload(TaxInvoice.customer),
                    selectinload(CreditNote.invoice).selectinload(TaxInvoice.lines),
                )
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

    async def list_page(
        self,
        *,
        limit: int,
        offset: int,
        q: Optional[str] = None,
    ) -> tuple[list[CreditNote], int]:
        invoice_alias = aliased(TaxInvoice)
        filters = []
        if q:
            pattern = f"%{q}%"
            filters.append(
                or_(
                    CreditNote.credit_note_number.ilike(pattern),
                    invoice_alias.invoice_number.ilike(pattern),
                    Customer.name.ilike(pattern),
                )
            )
        count_stmt = (
            select(func.count(CreditNote.id))
            .join(invoice_alias, CreditNote.invoice_id == invoice_alias.id)
            .join(Customer, invoice_alias.customer_id == Customer.id)
        )
        if filters:
            count_stmt = count_stmt.where(*filters)
        total = await self.db.scalar(count_stmt) or 0

        stmt = (
            select(CreditNote)
            .options(selectinload(CreditNote.invoice).selectinload(TaxInvoice.customer))
            .join(invoice_alias, CreditNote.invoice_id == invoice_alias.id)
            .join(Customer, invoice_alias.customer_id == Customer.id)
        )
        if filters:
            stmt = stmt.where(*filters)
        stmt = (
            stmt.order_by(
                CreditNote.issue_date.desc(),
                CreditNote.credit_note_number.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().unique().all()), total

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
