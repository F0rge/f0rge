from __future__ import annotations

import datetime
import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.comms_message import CommsMessageCRUD
from app.models.comms_message import (
    CommsChannel,
    CommsDocumentType,
    CommsMessage,
    CommsProvider,
    CommsStatus,
)
from app.schemas.comms import CommsMessageResponse
from f0rge_core.exceptions import NotFoundError
from f0rge_db.crud import unit_of_work


class CommsOutboxService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = CommsMessageCRUD(db)

    async def enqueue(
        self,
        *,
        channel: CommsChannel,
        provider: CommsProvider,
        document_type: CommsDocumentType,
        document_id: uuid.UUID,
        to_address: str,
        actor_user_id: Optional[uuid.UUID],
        from_identity: str = "",
        body_preview: Optional[str] = None,
    ) -> CommsMessage:
        row = CommsMessage(
            channel=channel,
            provider=provider,
            document_type=document_type,
            document_id=document_id,
            to_address=to_address,
            from_identity=from_identity,
            status=CommsStatus.PENDING,
            actor_user_id=actor_user_id,
            body_preview=body_preview,
        )
        async with unit_of_work(self.db):
            await self.crud.add_and_flush(row)
        return row

    async def mark_sent(
        self,
        message_id: uuid.UUID,
        *,
        from_identity: str,
        provider_message_id: Optional[str] = None,
    ) -> CommsMessage:
        row = await self._get(message_id)
        async with unit_of_work(self.db):
            row.status = CommsStatus.SENT
            row.sent_at = datetime.datetime.utcnow()
            row.from_identity = from_identity
            row.provider_message_id = provider_message_id
            row.error = None
        return row

    async def mark_failed(self, message_id: uuid.UUID, error: str) -> CommsMessage:
        row = await self._get(message_id)
        async with unit_of_work(self.db):
            row.status = CommsStatus.FAILED
            row.error = error[:2000]
        return row

    async def mark_opened(self, message_id: uuid.UUID, from_identity: str = "") -> CommsMessage:
        row = await self._get(message_id)
        async with unit_of_work(self.db):
            row.status = CommsStatus.OPENED
            row.sent_at = datetime.datetime.utcnow()
            if from_identity:
                row.from_identity = from_identity
        return row

    async def list_for_document(
        self,
        document_type: CommsDocumentType,
        document_id: uuid.UUID,
    ) -> list[CommsMessageResponse]:
        rows = await self.crud.list_for_document(document_type, document_id)
        return [self._to_response(row) for row in rows]

    async def _get(self, message_id: uuid.UUID) -> CommsMessage:
        row = await self.crud.get_by_id(message_id)
        if row is None:
            raise NotFoundError("Comms message not found")
        return row

    @staticmethod
    def _to_response(row: CommsMessage) -> CommsMessageResponse:
        return CommsMessageResponse(
            id=row.id,
            created_at=row.created_at,
            sent_at=row.sent_at,
            channel=row.channel.value,
            provider=row.provider.value,
            document_type=row.document_type.value,
            document_id=row.document_id,
            to_address=row.to_address,
            from_identity=row.from_identity,
            status=row.status.value,
            provider_message_id=row.provider_message_id,
            error=row.error,
        )
