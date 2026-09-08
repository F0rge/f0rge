from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.books_event import BooksDocumentType, BooksEvent
from f0rge_db.crud import BaseCRUD


class BooksEventCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def list_for_document(
        self,
        document_type: BooksDocumentType,
        document_id: uuid.UUID,
    ) -> list[BooksEvent]:
        result = await self.db.execute(
            select(BooksEvent)
            .where(
                BooksEvent.document_type == document_type,
                BooksEvent.document_id == document_id,
            )
            .order_by(BooksEvent.created_at.asc(), BooksEvent.id.asc())
        )
        return list(result.scalars().all())
