from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from app.dependencies.auth import (
    get_current_user_id,
    get_reorder_service,
    require_catalogue_mutate,
)
from app.schemas.reorder import ReorderDraftPoCreate, ReorderDraftPoResponse, ReorderItemResponse
from app.services.reorder import ReorderService

reorder_router = APIRouter(prefix="/api/v1/reorder", tags=["reorder"])


@reorder_router.get("", response_model=list[ReorderItemResponse])
async def list_reorder(
    _: uuid.UUID = Depends(get_current_user_id),
    service: ReorderService = Depends(get_reorder_service),
):
    return await service.list()


@reorder_router.post(
    "/draft-po",
    response_model=ReorderDraftPoResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_reorder_draft_po(
    body: ReorderDraftPoCreate,
    _: uuid.UUID = Depends(require_catalogue_mutate),
    service: ReorderService = Depends(get_reorder_service),
):
    return await service.create_draft_pos(body)
