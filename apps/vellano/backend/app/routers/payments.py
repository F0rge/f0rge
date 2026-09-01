from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from app.dependencies.auth import (
    get_current_user_id,
    get_payment_service,
    require_books_mutate,
)
from app.schemas.payment import PaymentCreate, PaymentResponse
from app.services.payments import PaymentService

payments_router = APIRouter(prefix="/api/v1/payments", tags=["payments"])


@payments_router.get("", response_model=list[PaymentResponse])
async def list_payments(
    _: uuid.UUID = Depends(get_current_user_id),
    service: PaymentService = Depends(get_payment_service),
):
    return await service.list()


@payments_router.post("", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
async def create_payment(
    body: PaymentCreate,
    user_id: uuid.UUID = Depends(require_books_mutate),
    service: PaymentService = Depends(get_payment_service),
):
    return await service.create(body, user_id)
