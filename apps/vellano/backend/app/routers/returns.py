from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from app.dependencies.auth import (
    get_current_user_id,
    get_stock_returns_service,
    require_returns_mutate,
)
from app.schemas.stock_return import StockReturnCreate, StockReturnResponse
from app.services.stock_returns import StockReturnsService

returns_router = APIRouter(prefix="/api/v1/returns", tags=["returns"])


@returns_router.get("", response_model=list[StockReturnResponse])
async def list_returns(
    _: uuid.UUID = Depends(get_current_user_id),
    service: StockReturnsService = Depends(get_stock_returns_service),
):
    return await service.list()


@returns_router.post(
    "",
    response_model=StockReturnResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_return(
    body: StockReturnCreate,
    user_id: uuid.UUID = Depends(require_returns_mutate),
    service: StockReturnsService = Depends(get_stock_returns_service),
):
    return await service.create(body, user_id)


@returns_router.get("/{return_id}", response_model=StockReturnResponse)
async def get_return(
    return_id: uuid.UUID,
    _: uuid.UUID = Depends(get_current_user_id),
    service: StockReturnsService = Depends(get_stock_returns_service),
):
    return await service.get(return_id)


@returns_router.post("/{return_id}/complete", response_model=StockReturnResponse)
async def complete_return(
    return_id: uuid.UUID,
    user_id: uuid.UUID = Depends(require_returns_mutate),
    service: StockReturnsService = Depends(get_stock_returns_service),
):
    return await service.complete(return_id, user_id)


@returns_router.post("/{return_id}/cancel", response_model=StockReturnResponse)
async def cancel_return(
    return_id: uuid.UUID,
    _: uuid.UUID = Depends(require_returns_mutate),
    service: StockReturnsService = Depends(get_stock_returns_service),
):
    return await service.cancel(return_id)
