from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from app.dependencies.auth import (
    get_adjustment_service,
    get_current_user_id,
    require_receive,
)
from app.schemas.stock_adjustment import (
    StockAdjustmentCreate,
    StockAdjustmentLineCreate,
    StockAdjustmentLineResponse,
    StockAdjustmentLineUpdate,
    StockAdjustmentResponse,
)
from app.services.stock_adjustments import StockAdjustmentService

adjustments_router = APIRouter(prefix="/api/v1/adjustments", tags=["adjustments"])


@adjustments_router.get("", response_model=list[StockAdjustmentResponse])
async def list_adjustments(
    _: uuid.UUID = Depends(get_current_user_id),
    service: StockAdjustmentService = Depends(get_adjustment_service),
):
    return await service.list()


@adjustments_router.post(
    "",
    response_model=StockAdjustmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_adjustment(
    body: StockAdjustmentCreate,
    user_id: uuid.UUID = Depends(require_receive),
    service: StockAdjustmentService = Depends(get_adjustment_service),
):
    return await service.create(body, user_id)


@adjustments_router.get("/{adjustment_id}", response_model=StockAdjustmentResponse)
async def get_adjustment(
    adjustment_id: uuid.UUID,
    _: uuid.UUID = Depends(get_current_user_id),
    service: StockAdjustmentService = Depends(get_adjustment_service),
):
    return await service.get(adjustment_id)


@adjustments_router.post(
    "/{adjustment_id}/lines",
    response_model=StockAdjustmentLineResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_adjustment_line(
    adjustment_id: uuid.UUID,
    body: StockAdjustmentLineCreate,
    _: uuid.UUID = Depends(require_receive),
    service: StockAdjustmentService = Depends(get_adjustment_service),
):
    return await service.add_line(adjustment_id, body)


@adjustments_router.patch(
    "/{adjustment_id}/lines/{line_id}",
    response_model=StockAdjustmentLineResponse,
)
async def update_adjustment_line(
    adjustment_id: uuid.UUID,
    line_id: uuid.UUID,
    body: StockAdjustmentLineUpdate,
    _: uuid.UUID = Depends(require_receive),
    service: StockAdjustmentService = Depends(get_adjustment_service),
):
    return await service.update_line(adjustment_id, line_id, body)


@adjustments_router.delete(
    "/{adjustment_id}/lines/{line_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_adjustment_line(
    adjustment_id: uuid.UUID,
    line_id: uuid.UUID,
    _: uuid.UUID = Depends(require_receive),
    service: StockAdjustmentService = Depends(get_adjustment_service),
):
    return await service.delete_line(adjustment_id, line_id)


@adjustments_router.post("/{adjustment_id}/complete", response_model=StockAdjustmentResponse)
async def complete_adjustment(
    adjustment_id: uuid.UUID,
    user_id: uuid.UUID = Depends(require_receive),
    service: StockAdjustmentService = Depends(get_adjustment_service),
):
    return await service.complete(adjustment_id, user_id)


@adjustments_router.post("/{adjustment_id}/cancel", response_model=StockAdjustmentResponse)
async def cancel_adjustment(
    adjustment_id: uuid.UUID,
    _: uuid.UUID = Depends(require_receive),
    service: StockAdjustmentService = Depends(get_adjustment_service),
):
    return await service.cancel(adjustment_id)
