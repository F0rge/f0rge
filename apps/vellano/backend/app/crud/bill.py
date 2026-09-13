from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.bill import Bill
from app.models.supplier import Supplier
from f0rge_db.crud import BaseCRUD


class BillCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_id(self, bill_id: uuid.UUID) -> Optional[Bill]:
        return (
            await self.db.execute(
                select(Bill)
                .options(
                    selectinload(Bill.supplier),
                    selectinload(Bill.lines),
                )
                .where(Bill.id == bill_id)
            )
        ).scalar_one_or_none()

    async def list_all(self) -> list[Bill]:
        result = await self.db.execute(
            select(Bill)
            .options(
                selectinload(Bill.supplier),
                selectinload(Bill.lines),
            )
            .order_by(Bill.bill_number)
        )
        return list(result.scalars().all())

    async def list_page(
        self,
        *,
        limit: int,
        offset: int,
        q: Optional[str] = None,
    ) -> tuple[list[Bill], int]:
        filters = []
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
            .options(selectinload(Bill.supplier))
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
        result = await self.db.execute(
            select(Bill.bill_number).order_by(Bill.bill_number.desc()).limit(1)
        )
        last = result.scalar_one_or_none()
        if last is None:
            return "BILL-0001"
        num = int(last.split("-")[1]) + 1
        return f"BILL-{num:04d}"
