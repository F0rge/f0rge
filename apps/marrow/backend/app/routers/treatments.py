from __future__ import annotations

import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, UploadFile, status

from app.dependencies.treatment_log import get_treatment_log_service
from app.dependencies.treatments import (
    get_treatment_extraction_orchestrator,
    get_treatment_service,
)
from app.middleware.auth import get_current_session
from app.schemas.treatment import (
    TreatmentCreate,
    TreatmentExtractionResult,
    TreatmentResponse,
    TreatmentUpdate,
)
from app.services.treatment_extraction_orchestrator import TreatmentExtractionOrchestrator
from app.schemas.treatment_log import ProtocolResponse, TreatmentLogResult, TreatmentLogUpdate
from app.services.treatment_log import TreatmentLogService
from app.services.treatments import TreatmentService

router = APIRouter(
    prefix="/api/v1/treatments",
    tags=["treatments"],
    dependencies=[Depends(get_current_session)],
)


@router.get("", response_model=list[TreatmentResponse])
async def list_treatments(
    active_on: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    service: TreatmentService = Depends(get_treatment_service),
):
    return await service.list(active_on)


# Must be declared before GET /{treatment_id} — otherwise "/protocol" is
# captured as treatment_id and fails int path-conversion.
@router.get("/protocol", response_model=ProtocolResponse)
async def get_protocol(
    date: Optional[datetime.date] = Query(None),
    service: TreatmentLogService = Depends(get_treatment_log_service),
):
    return await service.get_protocol(date)


@router.post("/extract-upload", response_model=TreatmentExtractionResult)
async def extract_treatment_upload(
    file: UploadFile,
    orchestrator: TreatmentExtractionOrchestrator = Depends(get_treatment_extraction_orchestrator),
):
    return await orchestrator.preview_upload(file)


@router.get("/{treatment_id}", response_model=TreatmentResponse)
async def get_treatment(
    treatment_id: int,
    service: TreatmentService = Depends(get_treatment_service),
):
    return await service.get(treatment_id)


@router.post("", response_model=TreatmentResponse, status_code=status.HTTP_201_CREATED)
async def create_treatment(
    body: TreatmentCreate,
    service: TreatmentService = Depends(get_treatment_service),
):
    return await service.create(body)


@router.put("/{treatment_id}", response_model=TreatmentResponse)
async def update_treatment(
    treatment_id: int,
    body: TreatmentUpdate,
    service: TreatmentService = Depends(get_treatment_service),
):
    return await service.update(treatment_id, body)


@router.put("/{treatment_id}/log", response_model=TreatmentLogResult)
async def log_treatment_dose(
    treatment_id: int,
    body: TreatmentLogUpdate,
    service: TreatmentLogService = Depends(get_treatment_log_service),
):
    return await service.upsert(treatment_id, body.date, body.doses_taken)


@router.delete("/{treatment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_treatment(
    treatment_id: int,
    service: TreatmentService = Depends(get_treatment_service),
):
    await service.delete(treatment_id)
