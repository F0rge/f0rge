from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document_sequence import DEFAULT_DOCUMENT_PADDING, DocumentSequence
from f0rge_db.crud import BaseCRUD

DOCUMENT_TYPE_DEFAULTS: dict[str, tuple[str, int]] = {
    "invoice": ("INV", DEFAULT_DOCUMENT_PADDING),
    "credit_note": ("CN", DEFAULT_DOCUMENT_PADDING),
    "bill": ("BILL", DEFAULT_DOCUMENT_PADDING),
    "payment": ("PAY", DEFAULT_DOCUMENT_PADDING),
    "purchase_order": ("PO", DEFAULT_DOCUMENT_PADDING),
    "delivery": ("DLV", DEFAULT_DOCUMENT_PADDING),
    "stock_return": ("RTN", DEFAULT_DOCUMENT_PADDING),
    "journal": ("JE", DEFAULT_DOCUMENT_PADDING),
    "layby": ("LB", DEFAULT_DOCUMENT_PADDING),
    "transfer": ("TRF", DEFAULT_DOCUMENT_PADDING),
    "pick": ("PCK", DEFAULT_DOCUMENT_PADDING),
    "quote": ("QT", DEFAULT_DOCUMENT_PADDING),
    "sales_order": ("SO", DEFAULT_DOCUMENT_PADDING),
}


class DocumentSequenceCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_team_and_type(
        self,
        team_id: uuid.UUID,
        doc_type: str,
    ) -> Optional[DocumentSequence]:
        result = await self.db.execute(
            select(DocumentSequence).where(
                DocumentSequence.team_id == team_id,
                DocumentSequence.doc_type == doc_type,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_team(self, team_id: uuid.UUID) -> list[DocumentSequence]:
        result = await self.db.execute(
            select(DocumentSequence)
            .where(DocumentSequence.team_id == team_id)
            .order_by(DocumentSequence.doc_type)
        )
        return list(result.scalars().all())
