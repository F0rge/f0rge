from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.bill import Bill
from app.models.supplier import Supplier
from f0rge_db.crud import BaseCRUD

_DETAIL = (selectinload(Bill.supplier), selectinload(Bill.lines), selectinload(Bill.attachments))


class BillCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_id(self, bill_id: uuid.UUID, *, for_update: bool = False) -> Optional[Bill]:
        # Always fresh: the session may already hold this bill with an older collection.
        stmt = (
            select(Bill)
            .options(*_DETAIL)
            .where(Bill.id == bill_id)
            .execution_options(populate_existing=True)
        )
        if for_update:
            stmt = stmt.with_for_update()
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def list_all(self, *, include_imported: bool = True) -> list[Bill]:
        stmt = select(Bill).options(*_DETAIL).order_by(Bill.bill_number)
        if not include_imported:
            stmt = stmt.where(Bill.is_archive.is_(False))
        return list((await self.db.execute(stmt)).scalars().all())

    async def list_page(
        self,
        *,
        limit: int,
        offset: int,
        q: Optional[str] = None,
    ) -> tuple[list[Bill], int]:
        filters = [Bill.is_archive.is_(False)]
        if q:
            pattern = f"%{q}%"
            filters.append(
                or_(
                    Bill.bill_number.ilike(pattern),
                    Bill.supplier_ref.ilike(pattern),
                    Supplier.name.ilike(pattern),
                )
            )
        count_stmt = select(func.count(Bill.id)).join(Supplier, Bill.supplier_id == Supplier.id)
        if filters:
            count_stmt = count_stmt.where(*filters)
        total = await self.db.scalar(count_stmt) or 0

        stmt = (
            select(Bill)
            .options(selectinload(Bill.supplier), selectinload(Bill.attachments))
            .join(Supplier, Bill.supplier_id == Supplier.id)
        )
        if filters:
            stmt = stmt.where(*filters)
        stmt = (
            stmt.order_by(Bill.issue_date.desc(), Bill.bill_number.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().unique().all()), total

    async def get_next_bill_number(self) -> str:
        from app.services.document_numbering import DocumentNumberingService

        return await DocumentNumberingService(self.db).allocate("bill")
