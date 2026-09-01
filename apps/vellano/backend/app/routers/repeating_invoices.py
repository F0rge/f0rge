from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from app.dependencies.auth import (
    get_current_user_id,
    get_repeating_invoice_service,
    require_books_mutate,
)
from app.schemas.repeating_invoice import (
    RepeatingInvoiceCreate,
    RepeatingInvoiceResponse,
    RepeatingInvoiceRunResponse,
    RepeatingInvoiceUpdate,
)
from app.services.repeating_invoices import RepeatingInvoiceService

repeating_invoices_router = APIRouter(
    prefix="/api/v1/repeating-invoices",
    tags=["repeating-invoices"],
)


@repeating_invoices_router.get("", response_model=list[RepeatingInvoiceResponse])
async def list_repeating_invoices(
    _: uuid.UUID = Depends(get_current_user_id),
    service: RepeatingInvoiceService = Depends(get_repeating_invoice_service),
):
    return await service.list()


@repeating_invoices_router.post(
    "",
    response_model=RepeatingInvoiceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_repeating_invoice(
    body: RepeatingInvoiceCreate,
    user_id: uuid.UUID = Depends(require_books_mutate),
    service: RepeatingInvoiceService = Depends(get_repeating_invoice_service),
):
    return await service.create(body, user_id)


@repeating_invoices_router.get("/{schedule_id}", response_model=RepeatingInvoiceResponse)
async def get_repeating_invoice(
    schedule_id: uuid.UUID,
    _: uuid.UUID = Depends(get_current_user_id),
    service: RepeatingInvoiceService = Depends(get_repeating_invoice_service),
):
    return await service.get(schedule_id)


@repeating_invoices_router.patch("/{schedule_id}", response_model=RepeatingInvoiceResponse)
async def update_repeating_invoice(
    schedule_id: uuid.UUID,
    body: RepeatingInvoiceUpdate,
    _: uuid.UUID = Depends(require_books_mutate),
    service: RepeatingInvoiceService = Depends(get_repeating_invoice_service),
):
    return await service.update(schedule_id, body)


@repeating_invoices_router.post(
    "/{schedule_id}/run",
    response_model=RepeatingInvoiceRunResponse,
    status_code=status.HTTP_201_CREATED,
)
async def run_repeating_invoice(
    schedule_id: uuid.UUID,
    _: uuid.UUID = Depends(require_books_mutate),
    service: RepeatingInvoiceService = Depends(get_repeating_invoice_service),
):
    return await service.run(schedule_id)
