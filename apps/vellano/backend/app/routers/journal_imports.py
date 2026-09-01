from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, UploadFile, status

from app.dependencies.auth import get_journal_import_service, require_books_mutate
from app.schemas.journal import JournalResponse
from app.schemas.journal_import import JournalImportPreviewResponse
from app.services.journal_imports import JournalImportService

journal_imports_router = APIRouter(
    prefix="/api/v1/journal-imports",
    tags=["journal-imports"],
)


@journal_imports_router.post("/preview", response_model=JournalImportPreviewResponse)
async def preview_journal_import(
    file: UploadFile = File(...),
    _: uuid.UUID = Depends(require_books_mutate),
    service: JournalImportService = Depends(get_journal_import_service),
):
    return await service.preview(file)


@journal_imports_router.post(
    "/commit",
    response_model=JournalResponse,
    status_code=status.HTTP_201_CREATED,
)
async def commit_journal_import(
    file: UploadFile = File(...),
    _: uuid.UUID = Depends(require_books_mutate),
    service: JournalImportService = Depends(get_journal_import_service),
):
    return await service.commit(file)
