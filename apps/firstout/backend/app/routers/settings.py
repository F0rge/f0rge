from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, UploadFile

from app.dependencies.auth import (
    get_current_user_id,
    get_payment_reminder_service,
    get_settings_service,
    require_owner,
    require_settings,
)
from app.schemas.payment_reminder import (
    PaymentReminderSettingsResponse,
    PaymentReminderSettingsUpdate,
)
from app.services.payment_reminders import PaymentReminderService
from app.schemas.comms import (
    CommsSettingsResponse,
    CommsSettingsUpdate,
    CommsTestEmailRequest,
    CommsTestEmailResponse,
)
from app.schemas.settings import SettingsResponse, SettingsUpdate
from app.services.settings import SettingsService

settings_router = APIRouter(prefix="/api/v1/settings", tags=["settings"])


@settings_router.get("", response_model=SettingsResponse)
async def get_settings(
    user_id: uuid.UUID = Depends(get_current_user_id),
    service: SettingsService = Depends(get_settings_service),
) -> SettingsResponse:
    return await service.get_for_user(user_id)


@settings_router.patch("", response_model=SettingsResponse)
async def update_settings(
    data: SettingsUpdate,
    user_id: uuid.UUID = Depends(require_settings),
    service: SettingsService = Depends(get_settings_service),
) -> SettingsResponse:
    return await service.update(user_id, data)


@settings_router.get("/comms", response_model=CommsSettingsResponse)
async def get_comms_settings(
    user_id: uuid.UUID = Depends(get_current_user_id),
    service: SettingsService = Depends(get_settings_service),
) -> CommsSettingsResponse:
    return await service.get_comms(user_id)


@settings_router.patch("/comms", response_model=CommsSettingsResponse)
async def update_comms_settings(
    data: CommsSettingsUpdate,
    user_id: uuid.UUID = Depends(require_settings),
    service: SettingsService = Depends(get_settings_service),
) -> CommsSettingsResponse:
    return await service.update_comms(user_id, data)


@settings_router.post("/comms/test-email", response_model=CommsTestEmailResponse)
async def test_comms_email(
    data: CommsTestEmailRequest,
    user_id: uuid.UUID = Depends(require_settings),
    service: SettingsService = Depends(get_settings_service),
) -> CommsTestEmailResponse:
    return await service.test_email(user_id, data)


@settings_router.get("/payment-reminders", response_model=PaymentReminderSettingsResponse)
async def get_payment_reminder_settings(
    _: uuid.UUID = Depends(require_owner),
    service: PaymentReminderService = Depends(get_payment_reminder_service),
) -> PaymentReminderSettingsResponse:
    return await service.get_settings()


@settings_router.patch("/payment-reminders", response_model=PaymentReminderSettingsResponse)
async def update_payment_reminder_settings(
    data: PaymentReminderSettingsUpdate,
    _: uuid.UUID = Depends(require_owner),
    service: PaymentReminderService = Depends(get_payment_reminder_service),
) -> PaymentReminderSettingsResponse:
    return await service.update_settings(data)


@settings_router.post("/logo", response_model=SettingsResponse)
async def upload_logo(
    logo: UploadFile = File(...),
    user_id: uuid.UUID = Depends(require_settings),
    service: SettingsService = Depends(get_settings_service),
) -> SettingsResponse:
    return await service.upload_logo(user_id, logo)


@settings_router.get("/logo")
async def get_logo(
    user_id: uuid.UUID = Depends(get_current_user_id),
    service: SettingsService = Depends(get_settings_service),
):
    return await service.serve_logo(user_id)
