from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends

from app.dependencies.auth import get_current_user_id, get_settings_service, require_settings
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
