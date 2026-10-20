"""Read a supplier proforma into a draft purchase order."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import ValidationError as PydanticValidationError

from app.dependencies.auth import get_document_intake_service, require_catalogue_mutate
from app.schemas.document_intake import (
    IntakeSkuCreate,
    IntakeSkuResponse,
    ProformaConfirmIn,
    ProformaConfirmResponse,
    ProformaReview,
    SkuSuggestIn,
    SkuSuggestion,
)
from app.services.document_intake.service import DocumentIntakeService
from f0rge_core.exceptions import ValidationError

document_intake_router = APIRouter(prefix="/api/v1/document-intake", tags=["document-intake"])


@document_intake_router.post("/proformas/extract", response_model=ProformaReview)
async def extract_proforma(
    file: UploadFile = File(...),
    _: uuid.UUID = Depends(require_catalogue_mutate),
    service: DocumentIntakeService = Depends(get_document_intake_service),
):
    return await service.extract_proforma(file)


@document_intake_router.post("/proformas/confirm", response_model=ProformaConfirmResponse)
async def confirm_proforma(
    file: UploadFile = File(...),
    payload: str = Form(...),
    user_id: uuid.UUID = Depends(require_catalogue_mutate),
    service: DocumentIntakeService = Depends(get_document_intake_service),
):
    try:
        data = ProformaConfirmIn.model_validate_json(payload)
    except PydanticValidationError as exc:
        raise ValidationError("Check the supplier, date, and lines before saving.") from exc
    return await service.confirm_proforma(file, data, user_id)


@document_intake_router.post("/sku-suggestions", response_model=SkuSuggestion)
async def suggest_sku(
    body: SkuSuggestIn,
    _: uuid.UUID = Depends(require_catalogue_mutate),
    service: DocumentIntakeService = Depends(get_document_intake_service),
):
    return await service.suggest_sku(body)


@document_intake_router.post("/skus", response_model=IntakeSkuResponse)
async def create_intake_sku(
    body: IntakeSkuCreate,
    user_id: uuid.UUID = Depends(require_catalogue_mutate),
    service: DocumentIntakeService = Depends(get_document_intake_service),
):
    return await service.create_sku(body, user_id)
