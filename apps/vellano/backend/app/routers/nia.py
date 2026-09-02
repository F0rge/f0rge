from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends

from app.dependencies.auth import get_current_user_id
from app.schemas.nia import NiaHealthResponse
from app.services.nia_health import NiaHealthService

nia_router = APIRouter(prefix="/api/v1/nia", tags=["nia"])


def get_nia_health_service() -> NiaHealthService:
    return NiaHealthService()


@nia_router.get("/health", response_model=NiaHealthResponse)
async def nia_health(
    _: uuid.UUID = Depends(get_current_user_id),
    service: NiaHealthService = Depends(get_nia_health_service),
) -> NiaHealthResponse:
    return service.health()
