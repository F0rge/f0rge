from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from fastapi.responses import Response

from app.dependencies.auth import (
    get_current_user_id,
    get_invoice_service,
    require_books_mutate,
)
from app.schemas.invoice import (
    ManualInvoiceCreate,
    InvoiceListItem,
    InvoicePreviewRequest,
    InvoiceResponse,
    InvoiceSummary,
    InvoiceUpdate,
)
from app.schemas.page import Page, PageParams, get_page_params
from app.schemas.sale_line_pricing import SalePricePreview
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
    body: ManualInvoiceCreate,
    user_id: uuid.UUID = Depends(require_books_mutate),
    service: InvoiceService = Depends(get_invoice_service),
):
    return await service.create_manual(body, user_id)


@invoices_router.post("/preview", response_model=SalePricePreview)
async def preview_invoice_prices(
    body: InvoicePreviewRequest,
    user_id: uuid.UUID = Depends(require_books_mutate),
    service: InvoiceService = Depends(get_invoice_service),
):
    return await service.preview(body, user_id)


@invoices_router.get("/summary", response_model=InvoiceSummary)
async def invoice_summary(
    _: uuid.UUID = Depends(get_current_user_id),
    service: InvoiceService = Depends(get_invoice_service),
):
    return await service.summary()


@invoices_router.get("/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(
    invoice_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    service: InvoiceService = Depends(get_invoice_service),
):
    return await service.get(invoice_id, user_id)


@invoices_router.patch("/{invoice_id}", response_model=InvoiceResponse)
async def update_invoice(
    invoice_id: uuid.UUID,
    body: InvoiceUpdate,
    user_id: uuid.UUID = Depends(require_books_mutate),
    service: InvoiceService = Depends(get_invoice_service),
):
    return await service.update(invoice_id, body, user_id)


@invoices_router.post("/{invoice_id}/archive", response_model=InvoiceResponse)
async def archive_invoice(
    invoice_id: uuid.UUID,
    user_id: uuid.UUID = Depends(require_books_mutate),
    service: InvoiceService = Depends(get_invoice_service),
):
    return await service.set_archived(invoice_id, True, user_id)


@invoices_router.post("/{invoice_id}/restore", response_model=InvoiceResponse)
async def restore_invoice(
    invoice_id: uuid.UUID,
    user_id: uuid.UUID = Depends(require_books_mutate),
    service: InvoiceService = Depends(get_invoice_service),
):
    return await service.set_archived(invoice_id, False, user_id)


@invoices_router.get("/{invoice_id}/pdf", response_model=None)
async def get_invoice_pdf(
    invoice_id: uuid.UUID,
    _: uuid.UUID = Depends(get_current_user_id),
    service: InvoiceService = Depends(get_invoice_service),
) -> Response:
    return await service.serve_pdf(invoice_id)
