from __future__ import annotations

import uuid
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import Response

from app.dependencies.auth import (
    get_current_user_id,
    get_payment_service,
    require_books_mutate,
)
from app.schemas.page import Page, PageParams, get_page_params
from app.schemas.payment import (
    PaymentCreate,
    PaymentOpenDocument,
    PaymentResponse,
    PaymentSummary,
    PaymentVoid,
)
from app.services.payments import PaymentService

payments_router = APIRouter(prefix="/api/v1/payments", tags=["payments"])


@payments_router.get("", response_model=Page[PaymentResponse])
async def list_payments(
    params: PageParams = Depends(get_page_params),
    invoice_id: Optional[uuid.UUID] = Query(None),
    bill_id: Optional[uuid.UUID] = Query(None),
    _: uuid.UUID = Depends(get_current_user_id),
    service: PaymentService = Depends(get_payment_service),
):
    return await service.list(params, invoice_id=invoice_id, bill_id=bill_id)


@payments_router.post("", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
async def create_payment(
    body: PaymentCreate,
    user_id: uuid.UUID = Depends(require_books_mutate),
    service: PaymentService = Depends(get_payment_service),
):
    return await service.create(body, user_id)


@payments_router.get("/summary", response_model=PaymentSummary)
async def payment_summary(
    _: uuid.UUID = Depends(get_current_user_id),
    service: PaymentService = Depends(get_payment_service),
):
    return await service.summary()


@payments_router.get("/open-documents", response_model=list[PaymentOpenDocument])
async def list_open_payment_documents(
    direction: Literal["in", "out"] = Query(...),
    _: uuid.UUID = Depends(require_books_mutate),
    service: PaymentService = Depends(get_payment_service),
):
    return await service.open_documents(direction)


@payments_router.post("/{payment_id}/void", response_model=PaymentResponse)
async def void_payment(
    payment_id: uuid.UUID,
    body: PaymentVoid,
    user_id: uuid.UUID = Depends(require_books_mutate),
    service: PaymentService = Depends(get_payment_service),
):
    return await service.void(payment_id, body.reason, user_id)


@payments_router.get("/{payment_id}/pdf", response_model=None)
async def get_payment_pdf(
    payment_id: uuid.UUID,
    _: uuid.UUID = Depends(get_current_user_id),
    service: PaymentService = Depends(get_payment_service),
) -> Response:
    return await service.serve_pdf(payment_id)
