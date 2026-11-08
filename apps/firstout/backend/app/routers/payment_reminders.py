from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from app.dependencies.auth import (
    get_current_user_id,
    get_payment_reminder_service,
    require_books_mutate,
)
from app.schemas.payment_reminder import (
    ReminderActionRequest,
    ReminderBoard,
    ReminderOptOutRequest,
    ReminderOptOutResponse,
    ReminderPauseResponse,
    ReminderRow,
)
from app.services.payment_reminders import PaymentReminderService

payment_reminders_router = APIRouter(prefix="/api/v1/payment-reminders", tags=["payment-reminders"])


@payment_reminders_router.get("", response_model=ReminderBoard)
async def reminder_board(
    _: uuid.UUID = Depends(get_current_user_id),
    service: PaymentReminderService = Depends(get_payment_reminder_service),
) -> ReminderBoard:
    return await service.board()


@payment_reminders_router.post("/send-now", response_model=ReminderRow)
async def send_reminder_now(
    body: ReminderActionRequest,
    user_id: uuid.UUID = Depends(require_books_mutate),
    service: PaymentReminderService = Depends(get_payment_reminder_service),
) -> ReminderRow:
    return await service.send_now(body, user_id)


@payment_reminders_router.post("/skip", response_model=ReminderRow)
async def skip_reminder(
    body: ReminderActionRequest,
    user_id: uuid.UUID = Depends(require_books_mutate),
    service: PaymentReminderService = Depends(get_payment_reminder_service),
) -> ReminderRow:
    return await service.skip(body, user_id)


@payment_reminders_router.post(
    "/invoices/{invoice_id}/pause",
    response_model=ReminderPauseResponse,
)
async def pause_invoice_reminders(
    invoice_id: uuid.UUID,
    _: uuid.UUID = Depends(require_books_mutate),
    service: PaymentReminderService = Depends(get_payment_reminder_service),
) -> ReminderPauseResponse:
    return await service.set_paused(invoice_id, True)


@payment_reminders_router.post(
    "/invoices/{invoice_id}/resume",
    response_model=ReminderPauseResponse,
)
async def resume_invoice_reminders(
    invoice_id: uuid.UUID,
    _: uuid.UUID = Depends(require_books_mutate),
    service: PaymentReminderService = Depends(get_payment_reminder_service),
) -> ReminderPauseResponse:
    return await service.set_paused(invoice_id, False)


@payment_reminders_router.post(
    "/customers/{customer_id}/opt-out",
    response_model=ReminderOptOutResponse,
    status_code=status.HTTP_200_OK,
)
async def set_customer_reminder_opt_out(
    customer_id: uuid.UUID,
    body: ReminderOptOutRequest,
    _: uuid.UUID = Depends(require_books_mutate),
    service: PaymentReminderService = Depends(get_payment_reminder_service),
) -> ReminderOptOutResponse:
    return await service.set_opt_out(customer_id, body.opt_out)
