"""Read a supplier proforma into a purchase order, and a supplier invoice into a bill."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import ValidationError as PydanticValidationError

from app.dependencies.auth import (
    get_document_intake_service,
    get_invoice_intake_service,
    require_books_mutate,
    require_catalogue_mutate,
)
from app.schemas.document_intake import (
    IntakeSkuCreate,
    IntakeSkuResponse,
    InvoiceProcessIn,
    InvoiceReview,
    ProcessedBillOut,
    ProformaConfirmIn,
    ProformaConfirmResponse,
    ProformaReview,
    SkuSuggestIn,
    SkuSuggestion,
)
from app.services.document_intake.invoice_flow import InvoiceIntakeService
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


@document_intake_router.post("/invoices/extract", response_model=InvoiceReview)
async def extract_invoice(
    file: UploadFile = File(...),
    user_id: uuid.UUID = Depends(require_books_mutate),
    service: InvoiceIntakeService = Depends(get_invoice_intake_service),
):
    return await service.extract_invoice(file, user_id)


@document_intake_router.post("/invoices/process", response_model=ProcessedBillOut)
async def process_invoice(
    file: UploadFile = File(...),
    payload: str = Form(...),
    user_id: uuid.UUID = Depends(require_books_mutate),
    service: InvoiceIntakeService = Depends(get_invoice_intake_service),
):
    try:
        data = InvoiceProcessIn.model_validate_json(payload)
    except PydanticValidationError as exc:
        raise ValidationError(
            "Check the supplier, purchase order, date, and lines before posting."
        ) from exc
    return await service.process_invoice(file, data, user_id)
