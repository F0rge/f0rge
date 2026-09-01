from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from app.dependencies.auth import (
    get_current_user_id,
    get_journal_service,
    require_books_mutate,
)
from app.schemas.journal import JournalCreate, JournalResponse
from app.services.journals import JournalService

journals_router = APIRouter(prefix="/api/v1/journals", tags=["journals"])


@journals_router.get("", response_model=list[JournalResponse])
async def list_journals(
    _: uuid.UUID = Depends(get_current_user_id),
    service: JournalService = Depends(get_journal_service),
):
    return await service.list()


@journals_router.post("", response_model=JournalResponse, status_code=status.HTTP_201_CREATED)
async def create_journal(
    body: JournalCreate,
    user_id: uuid.UUID = Depends(require_books_mutate),
    service: JournalService = Depends(get_journal_service),
):
    return await service.create(body, user_id)


@journals_router.get("/{journal_id}", response_model=JournalResponse)
async def get_journal(
    journal_id: uuid.UUID,
    _: uuid.UUID = Depends(get_current_user_id),
    service: JournalService = Depends(get_journal_service),
):
    return await service.get(journal_id)


@journals_router.post("/{journal_id}/post", response_model=JournalResponse)
async def post_journal(
    journal_id: uuid.UUID,
    user_id: uuid.UUID = Depends(require_books_mutate),
    service: JournalService = Depends(get_journal_service),
):
    return await service.post(journal_id, user_id)


@journals_router.post("/{journal_id}/void", response_model=JournalResponse)
async def void_journal(
    journal_id: uuid.UUID,
    user_id: uuid.UUID = Depends(require_books_mutate),
    service: JournalService = Depends(get_journal_service),
):
    return await service.void(journal_id, user_id)
