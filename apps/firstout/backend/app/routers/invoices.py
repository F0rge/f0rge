from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from fastapi.responses import Response

from app.dependencies.auth import (
    get_comms_send_service,
    get_current_user_id,
    get_invoice_service,
    require_books_mutate,
    require_comms_send,
)
from app.schemas.comms import CommsSendRequest, CommsSendResponse
from app.schemas.invoice import InvoiceCreate, InvoiceListItem, InvoiceResponse
from app.schemas.page import Page, PageParams, get_page_params
from app.services.comms.send import CommsSendService
from app.services.invoices import InvoiceService

invoices_router = APIRouter(prefix="/api/v1/invoices", tags=["invoices"])


@invoices_router.get("", response_model=Page[InvoiceListItem])
async def list_invoices(
    params: PageParams = Depends(get_page_params),
    _: uuid.UUID = Depends(get_current_user_id),
    service: InvoiceService = Depends(get_invoice_service),
):
    return await service.list(params)


@invoices_router.post("", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED)
async def create_invoice(
    body: InvoiceCreate,
    user_id: uuid.UUID = Depends(require_books_mutate),
    service: InvoiceService = Depends(get_invoice_service),
):
    return await service.create(body, user_id)


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


@invoices_router.post("/{invoice_id}/send", response_model=CommsSendResponse)
async def send_invoice(
    invoice_id: uuid.UUID,
    body: CommsSendRequest,
    user_id: uuid.UUID = Depends(require_comms_send),
    service: CommsSendService = Depends(get_comms_send_service),
) -> CommsSendResponse:
    return await service.send_invoice(invoice_id, body, user_id)
