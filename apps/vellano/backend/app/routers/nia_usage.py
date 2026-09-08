from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends

from app.dependencies.auth import (
    get_nia_caps_service,
    require_nia_admin,
    require_nia_use,
)
from app.schemas.nia import NiaUsageCapUpdate, NiaUsageMeResponse, NiaUsageUserResponse
from app.services.nia_caps import NiaCapsService

nia_usage_router = APIRouter(prefix="/api/v1/nia/usage", tags=["nia"])


@nia_usage_router.get("/me", response_model=NiaUsageMeResponse)
async def get_my_nia_usage(
    user_id: uuid.UUID = Depends(require_nia_use),
    service: NiaCapsService = Depends(get_nia_caps_service),
) -> NiaUsageMeResponse:
    row = await service.get_my_usage(user_id)
    return NiaUsageMeResponse(**row)


@nia_usage_router.get("", response_model=list[NiaUsageUserResponse])
async def list_nia_usage(
    user_id: uuid.UUID = Depends(require_nia_admin),
    service: NiaCapsService = Depends(get_nia_caps_service),
) -> list[NiaUsageUserResponse]:
    rows = await service.list_team_usage(user_id)
    return [NiaUsageUserResponse(**row) for row in rows]


@nia_usage_router.patch("/{target_user_id}", response_model=NiaUsageUserResponse)
async def update_user_nia_cap(
    target_user_id: uuid.UUID,
    data: NiaUsageCapUpdate,
    user_id: uuid.UUID = Depends(require_nia_admin),
    service: NiaCapsService = Depends(get_nia_caps_service),
) -> NiaUsageUserResponse:
    row = await service.update_user_cap(user_id, target_user_id, data.nia_monthly_token_cap)
    return NiaUsageUserResponse(**row)
