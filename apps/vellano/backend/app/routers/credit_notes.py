from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from fastapi.responses import Response

from app.dependencies.auth import (
    get_credit_note_service,
    get_current_user_id,
    require_books_mutate,
)
from app.schemas.credit_note import CreditNoteCreate, CreditNoteResponse
from app.services.credit_notes import CreditNoteService

credit_notes_router = APIRouter(prefix="/api/v1/credit-notes", tags=["credit-notes"])


@credit_notes_router.get("", response_model=list[CreditNoteResponse])
async def list_credit_notes(
    _: uuid.UUID = Depends(get_current_user_id),
    service: CreditNoteService = Depends(get_credit_note_service),
):
    return await service.list()


@credit_notes_router.post(
    "", response_model=CreditNoteResponse, status_code=status.HTTP_201_CREATED
)
async def create_credit_note(
    body: CreditNoteCreate,
    _: uuid.UUID = Depends(require_books_mutate),
    service: CreditNoteService = Depends(get_credit_note_service),
):
    return await service.create(body)


@credit_notes_router.get("/{credit_note_id}", response_model=CreditNoteResponse)
async def get_credit_note(
    credit_note_id: uuid.UUID,
    _: uuid.UUID = Depends(get_current_user_id),
    service: CreditNoteService = Depends(get_credit_note_service),
):
    return await service.get(credit_note_id)


@credit_notes_router.get("/{credit_note_id}/pdf", response_model=None)
async def get_credit_note_pdf(
    credit_note_id: uuid.UUID,
    _: uuid.UUID = Depends(get_current_user_id),
    service: CreditNoteService = Depends(get_credit_note_service),
) -> Response:
    return await service.serve_pdf(credit_note_id)
