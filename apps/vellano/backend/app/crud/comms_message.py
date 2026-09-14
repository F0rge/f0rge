from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.comms_message import CommsDocumentType, CommsMessage
from f0rge_db.crud import BaseCRUD


class CommsMessageCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_provider_message_id(self, provider_message_id: str) -> Optional[CommsMessage]:
        result = await self.db.execute(
            select(CommsMessage).where(CommsMessage.provider_message_id == provider_message_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, message_id: uuid.UUID) -> Optional[CommsMessage]:
        result = await self.db.execute(select(CommsMessage).where(CommsMessage.id == message_id))
        return result.scalar_one_or_none()

    async def list_for_document(
        self,
        document_type: CommsDocumentType,
        document_id: uuid.UUID,
    ) -> list[CommsMessage]:
        result = await self.db.execute(
            select(CommsMessage)
            .where(
                CommsMessage.document_type == document_type,
                CommsMessage.document_id == document_id,
            )
            .order_by(CommsMessage.created_at.desc())
        )
        return list(result.scalars().all())
