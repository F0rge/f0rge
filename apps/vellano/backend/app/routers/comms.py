from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends

from app.dependencies.auth import get_comms_outbox_service, require_comms_send
from app.models.comms_message import CommsDocumentType
from app.schemas.comms import CommsMessageResponse
from app.services.comms.outbox import CommsOutboxService

comms_router = APIRouter(prefix="/api/v1/comms", tags=["comms"])


@comms_router.get("/messages", response_model=list[CommsMessageResponse])
async def list_comms_messages(
    document_type: CommsDocumentType,
    document_id: uuid.UUID,
    _: uuid.UUID = Depends(require_comms_send),
    service: CommsOutboxService = Depends(get_comms_outbox_service),
) -> list[CommsMessageResponse]:
    return await service.list_for_document(document_type, document_id)
