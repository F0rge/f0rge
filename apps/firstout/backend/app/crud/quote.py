from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.customer import Customer
from app.models.quote import Quote, QuoteLine, QuoteStatus
from f0rge_db.crud import BaseCRUD


class QuoteCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_id(self, quote_id: uuid.UUID) -> Optional[Quote]:
        return (
            await self.db.execute(
                select(Quote)
                .options(
                    selectinload(Quote.customer),
                    selectinload(Quote.lines).selectinload(QuoteLine.sku),
                )
                .where(Quote.id == quote_id)
            )
        ).scalar_one_or_none()

    async def list_page(
        self,
        *,
        limit: int,
        offset: int,
        q: Optional[str] = None,
        status: Optional[QuoteStatus] = None,
    ) -> tuple[list[Quote], int]:
        filters = []
        if q:
            pattern = f"%{q}%"
            filters.append(
                or_(
                    Quote.quote_number.ilike(pattern),
                    Customer.name.ilike(pattern),
                )
            )
        if status is not None:
            filters.append(Quote.status == status)

        count_stmt = select(func.count(Quote.id)).join(Customer, Quote.customer_id == Customer.id)
        if filters:
            count_stmt = count_stmt.where(*filters)
        total = await self.db.scalar(count_stmt) or 0

        stmt = (
            select(Quote)
            .options(
                selectinload(Quote.customer),
                selectinload(Quote.lines).selectinload(QuoteLine.sku),
            )
            .join(Customer, Quote.customer_id == Customer.id)
        )
        if filters:
            stmt = stmt.where(*filters)
        stmt = (
            stmt.order_by(Quote.created_at.desc(), Quote.quote_number.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().unique().all()), total

    async def get_next_quote_number(self) -> str:
        from app.services.document_numbering import DocumentNumberingService

        return await DocumentNumberingService(self.db).allocate("quote")
