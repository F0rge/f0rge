from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, UploadFile, status

from app.dependencies.auth import (
    get_bank_import_service,
    get_current_user_id,
    require_books_mutate,
)
from app.schemas.bank_import import (
    BankImportLineResponse,
    BankImportMatchRequest,
    BankImportResponse,
    BankImportSummary,
)
from app.services.bank_imports import BankImportService

bank_imports_router = APIRouter(prefix="/api/v1/bank-imports", tags=["bank-imports"])


@bank_imports_router.get("", response_model=list[BankImportSummary])
async def list_bank_imports(
    _: uuid.UUID = Depends(get_current_user_id),
    service: BankImportService = Depends(get_bank_import_service),
):
    return await service.list()


@bank_imports_router.post(
    "", response_model=BankImportResponse, status_code=status.HTTP_201_CREATED
)
async def upload_bank_import(
    file: UploadFile = File(...),
    _: uuid.UUID = Depends(require_books_mutate),
    service: BankImportService = Depends(get_bank_import_service),
):
    content = await file.read()
    filename = file.filename or "import.csv"
    return await service.create_from_csv(filename, content)


@bank_imports_router.get("/unmatched-lines", response_model=list[BankImportLineResponse])
async def list_unmatched_lines(
    _: uuid.UUID = Depends(get_current_user_id),
    service: BankImportService = Depends(get_bank_import_service),
):
    return await service.list_unmatched_lines()


@bank_imports_router.get("/{import_id}", response_model=BankImportResponse)
async def get_bank_import(
    import_id: uuid.UUID,
    _: uuid.UUID = Depends(get_current_user_id),
    service: BankImportService = Depends(get_bank_import_service),
):
    return await service.get(import_id)


@bank_imports_router.post(
    "/{import_id}/lines/{line_id}/match",
    response_model=BankImportLineResponse,
)
async def match_bank_line(
    import_id: uuid.UUID,
    line_id: uuid.UUID,
    body: BankImportMatchRequest,
    _: uuid.UUID = Depends(require_books_mutate),
    service: BankImportService = Depends(get_bank_import_service),
):
    return await service.match_line(import_id, line_id, body)
