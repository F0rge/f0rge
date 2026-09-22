from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, status
from fastapi.responses import Response

from app.dependencies.auth import (
    get_comms_send_service,
    get_current_user_id,
    get_layby_service,
    require_comms_send,
    require_laybys,
)
from app.models.layby import LaybyStatus
from app.schemas.comms import CommsSendRequest, CommsSendResponse
from app.schemas.layby import LaybyCreate, LaybyListItem, LaybyPaymentCreate, LaybyResponse
from app.schemas.page import Page, PageParams, get_page_params
from app.services.comms.send import CommsSendService
from app.services.laybys import LaybysService

laybys_router = APIRouter(prefix="/api/v1/laybys", tags=["laybys"])


@laybys_router.get("", response_model=Page[LaybyListItem])
async def list_laybys(
    params: PageParams = Depends(get_page_params),
    status: Optional[LaybyStatus] = None,
    _: uuid.UUID = Depends(get_current_user_id),
    service: LaybysService = Depends(get_layby_service),
):
    return await service.list(params, status=status)


@laybys_router.post(
    "",
    response_model=LaybyResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_layby(
    body: LaybyCreate,
    user_id: uuid.UUID = Depends(require_laybys),
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


@laybys_router.get("/{layby_id}/pdf", response_model=None)
async def get_layby_pdf(
    layby_id: uuid.UUID,
    _: uuid.UUID = Depends(get_current_user_id),
    service: LaybysService = Depends(get_layby_service),
) -> Response:
    return await service.serve_pdf(layby_id)


@laybys_router.post("/{layby_id}/send", response_model=CommsSendResponse)
async def send_layby(
    layby_id: uuid.UUID,
    body: CommsSendRequest,
    user_id: uuid.UUID = Depends(require_comms_send),
    service: CommsSendService = Depends(get_comms_send_service),
) -> CommsSendResponse:
    return await service.send_layby(layby_id, body, user_id)


@laybys_router.post(
    "/{layby_id}/payments",
    response_model=LaybyResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_layby_payment(
    layby_id: uuid.UUID,
    body: LaybyPaymentCreate,
    user_id: uuid.UUID = Depends(require_laybys),
    service: LaybysService = Depends(get_layby_service),
):
    return await service.add_payment(layby_id, body, user_id)


@laybys_router.post("/{layby_id}/complete", response_model=LaybyResponse)
async def complete_layby(
    layby_id: uuid.UUID,
    user_id: uuid.UUID = Depends(require_laybys),
    service: LaybysService = Depends(get_layby_service),
):
    return await service.complete(layby_id, user_id)


@laybys_router.post("/{layby_id}/cancel", response_model=LaybyResponse)
async def cancel_layby(
    layby_id: uuid.UUID,
    user_id: uuid.UUID = Depends(require_laybys),
    service: LaybysService = Depends(get_layby_service),
):
    return await service.cancel(layby_id, user_id)
