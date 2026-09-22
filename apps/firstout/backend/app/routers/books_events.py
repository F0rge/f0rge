from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query

from app.dependencies.auth import get_books_event_service, get_current_user_id
from app.models.books_event import BooksDocumentType
from app.schemas.books_event import BooksEventResponse
from app.services.books_events import BooksEventService

books_events_router = APIRouter(prefix="/api/v1/books-events", tags=["books-events"])


@books_events_router.get("", response_model=list[BooksEventResponse])
async def list_books_events(
    document_type: BooksDocumentType = Query(...),
    document_id: uuid.UUID = Query(...),
    _: uuid.UUID = Depends(get_current_user_id),
    service: BooksEventService = Depends(get_books_event_service),
):
    return await service.list(document_type, document_id)
