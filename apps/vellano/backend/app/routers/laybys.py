from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from app.dependencies.auth import get_current_user_id, get_layby_service, require_till
from app.schemas.layby import LaybyCreate, LaybyPaymentCreate, LaybyResponse
from app.services.laybys import LaybysService

laybys_router = APIRouter(prefix="/api/v1/laybys", tags=["laybys"])


@laybys_router.get("", response_model=list[LaybyResponse])
async def list_laybys(
    _: uuid.UUID = Depends(get_current_user_id),
    service: LaybysService = Depends(get_layby_service),
):
    return await service.list()


@laybys_router.post(
    "",
    response_model=LaybyResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_layby(
    body: LaybyCreate,
    user_id: uuid.UUID = Depends(require_till),
    service: LaybysService = Depends(get_layby_service),
):
    return await service.create(body, user_id)


@laybys_router.get("/{layby_id}", response_model=LaybyResponse)
async def get_layby(
    layby_id: uuid.UUID,
    _: uuid.UUID = Depends(get_current_user_id),
    service: LaybysService = Depends(get_layby_service),
):
    return await service.get(layby_id)


@laybys_router.post(
    "/{layby_id}/payments",
    response_model=LaybyResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_layby_payment(
    layby_id: uuid.UUID,
    body: LaybyPaymentCreate,
    user_id: uuid.UUID = Depends(require_till),
    service: LaybysService = Depends(get_layby_service),
):
    return await service.add_payment(layby_id, body, user_id)


@laybys_router.post("/{layby_id}/complete", response_model=LaybyResponse)
async def complete_layby(
    layby_id: uuid.UUID,
    user_id: uuid.UUID = Depends(require_till),
    service: LaybysService = Depends(get_layby_service),
):
    return await service.complete(layby_id, user_id)


@laybys_router.post("/{layby_id}/cancel", response_model=LaybyResponse)
async def cancel_layby(
    layby_id: uuid.UUID,
    user_id: uuid.UUID = Depends(require_till),
    service: LaybysService = Depends(get_layby_service),
):
    return await service.cancel(layby_id, user_id)
