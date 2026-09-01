from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from fastapi.responses import Response

from app.dependencies.auth import (
    get_current_user_id,
    get_pick_service,
    require_picks_mutate,
)
from app.schemas.pick import (
    PickComplete,
    PickConfirm,
    PickCreate,
    PickPreviewRequest,
    PickPreviewResponse,
    PickResponse,
    PickUpdate,
)
from app.services.picks import PickService

picks_router = APIRouter(prefix="/api/v1/picks", tags=["picks"])


@picks_router.post("/preview", response_model=PickPreviewResponse)
async def preview_pick(
    data: PickPreviewRequest,
    user_id: uuid.UUID = Depends(require_picks_mutate),
    service: PickService = Depends(get_pick_service),
):
    return await service.preview(data, user_id)


@picks_router.post("", response_model=PickResponse, status_code=status.HTTP_201_CREATED)
async def create_pick(
    data: PickCreate,
    user_id: uuid.UUID = Depends(require_picks_mutate),
    service: PickService = Depends(get_pick_service),
):
    return await service.create(data, user_id)


@picks_router.get("", response_model=list[PickResponse])
async def list_picks(
    _: uuid.UUID = Depends(get_current_user_id),
    service: PickService = Depends(get_pick_service),
):
    return await service.list()


@picks_router.get("/{pick_id}", response_model=PickResponse)
async def get_pick(
    pick_id: uuid.UUID,
    _: uuid.UUID = Depends(get_current_user_id),
    service: PickService = Depends(get_pick_service),
):
    return await service.get(pick_id)


@picks_router.patch("/{pick_id}", response_model=PickResponse)
async def update_pick(
    pick_id: uuid.UUID,
    data: PickUpdate,
    _: uuid.UUID = Depends(require_picks_mutate),
    service: PickService = Depends(get_pick_service),
):
    return await service.update(pick_id, data)


@picks_router.post("/{pick_id}/confirm", response_model=PickResponse)
async def confirm_pick(
    pick_id: uuid.UUID,
    data: PickConfirm,
    user_id: uuid.UUID = Depends(require_picks_mutate),
    service: PickService = Depends(get_pick_service),
):
    return await service.confirm(pick_id, data, user_id)


@picks_router.get("/{pick_id}/pdf", response_model=None)
async def get_pick_pdf(
    pick_id: uuid.UUID,
    _: uuid.UUID = Depends(get_current_user_id),
    service: PickService = Depends(get_pick_service),
) -> Response:
    return await service.serve_pdf(pick_id)


@picks_router.post("/{pick_id}/complete", response_model=PickResponse)
async def complete_pick(
    pick_id: uuid.UUID,
    data: PickComplete,
    user_id: uuid.UUID = Depends(require_picks_mutate),
    service: PickService = Depends(get_pick_service),
):
    return await service.complete(pick_id, data, user_id)


@picks_router.post("/{pick_id}/cancel", response_model=PickResponse)
async def cancel_pick(
    pick_id: uuid.UUID,
    _: uuid.UUID = Depends(require_picks_mutate),
    service: PickService = Depends(get_pick_service),
):
    return await service.cancel(pick_id)
