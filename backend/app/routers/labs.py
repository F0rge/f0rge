from __future__ import annotations

import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, UploadFile, status

from app.dependencies.labs import (
    get_lab_extraction_orchestrator,
    get_lab_import_service,
    get_labs_service,
)
from app.middleware.auth import get_current_session
from app.schemas.lab import (
    LabCreate,
    LabExtractRequest,
    LabImportRequest,
    LabResponse,
    LabUpdate,
)
from app.schemas.lab_marker import ExtractionResult
from app.services.lab_extraction_orchestrator import LabExtractionOrchestrator
from app.services.lab_import import LabImportService
from app.services.labs import LabsService

router = APIRouter(
    prefix="/api/v1/labs",
    tags=["labs"],
    dependencies=[Depends(get_current_session)],
)


@router.get("", response_model=List[LabResponse])
async def list_labs(
    start_date: Optional[datetime.date] = Query(None),
    end_date: Optional[datetime.date] = Query(None),
    lab_type: Optional[str] = Query(None, alias="type"),
    service: LabsService = Depends(get_labs_service),
):
    return await service.list_labs(start_date, end_date, lab_type)


@router.get("/{lab_id}", response_model=LabResponse)
async def get_lab(lab_id: int, service: LabsService = Depends(get_labs_service)):
    return await service.get_lab(lab_id)


@router.post("", response_model=LabResponse, status_code=status.HTTP_201_CREATED)
async def create_lab(body: LabCreate, service: LabsService = Depends(get_labs_service)):
    return await service.create_lab(body)


@router.put("/{lab_id}", response_model=LabResponse)
async def update_lab(
    lab_id: int,
    body: LabUpdate,
    service: LabsService = Depends(get_labs_service),
):
    return await service.update_lab(lab_id, body)


@router.delete("/{lab_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lab(lab_id: int, service: LabsService = Depends(get_labs_service)):
    await service.delete_lab(lab_id)


@router.post("/extract", response_model=ExtractionResult)
async def extract_lab_text(
    body: LabExtractRequest,
    orchestrator: LabExtractionOrchestrator = Depends(get_lab_extraction_orchestrator),
):
    return await orchestrator.preview_text(body.document_text)


@router.post("/extract-upload", response_model=ExtractionResult)
async def extract_lab_upload(
    file: UploadFile,
    orchestrator: LabExtractionOrchestrator = Depends(get_lab_extraction_orchestrator),
):
    return await orchestrator.preview_upload(file)


@router.post("/import", response_model=LabResponse, status_code=status.HTTP_201_CREATED)
async def import_lab_text(
    body: LabImportRequest,
    import_service: LabImportService = Depends(get_lab_import_service),
):
    return await import_service.import_from_text(body.document_text, body.source_path, body.force)


@router.post(
    "/import-upload",
    response_model=LabResponse,
    status_code=status.HTTP_201_CREATED,
)
async def import_lab_upload(
    file: UploadFile,
    force: bool = Query(False),
    import_service: LabImportService = Depends(get_lab_import_service),
):
    return await import_service.import_from_upload(file, force)
