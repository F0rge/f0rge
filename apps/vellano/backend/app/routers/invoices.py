from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from fastapi.responses import Response

from app.dependencies.auth import (
    get_current_user_id,
    get_invoice_service,
    require_books_mutate,
)
from app.schemas.invoice import InvoiceCreate, InvoiceResponse
from app.services.invoices import InvoiceService

invoices_router = APIRouter(prefix="/api/v1/invoices", tags=["invoices"])


@invoices_router.get("", response_model=list[InvoiceResponse])
async def list_invoices(
    _: uuid.UUID = Depends(get_current_user_id),
    service: InvoiceService = Depends(get_invoice_service),
):
    return await service.list()


@invoices_router.post("", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED)
async def create_invoice(
    body: InvoiceCreate,
    _: uuid.UUID = Depends(require_books_mutate),
    service: InvoiceService = Depends(get_invoice_service),
):
    return await service.create(body)


@invoices_router.get("/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(
    invoice_id: uuid.UUID,
    _: uuid.UUID = Depends(get_current_user_id),
    service: InvoiceService = Depends(get_invoice_service),
):
    return await service.get(invoice_id)


@invoices_router.get("/{invoice_id}/pdf", response_model=None)
async def get_invoice_pdf(
    invoice_id: uuid.UUID,
    _: uuid.UUID = Depends(get_current_user_id),
    service: InvoiceService = Depends(get_invoice_service),
) -> Response:
    return await service.serve_pdf(invoice_id)
