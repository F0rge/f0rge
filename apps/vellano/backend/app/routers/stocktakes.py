from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from app.dependencies.auth import (
    get_current_user_id,
    get_stocktake_service,
    require_receive,
)
from app.schemas.stocktake import (
    StocktakeCreate,
    StocktakeLineCountUpdate,
    StocktakeLineResponse,
    StocktakeLookupRequest,
    StocktakeResponse,
)
from app.services.stocktakes import StocktakeService

stocktakes_router = APIRouter(prefix="/api/v1/stocktakes", tags=["stocktakes"])


@stocktakes_router.get("", response_model=list[StocktakeResponse])
async def list_stocktakes(
    _: uuid.UUID = Depends(get_current_user_id),
    service: StocktakeService = Depends(get_stocktake_service),
):
    return await service.list()


@stocktakes_router.post("", response_model=StocktakeResponse, status_code=status.HTTP_201_CREATED)
async def start_stocktake(
    body: StocktakeCreate,
    user_id: uuid.UUID = Depends(require_receive),
    service: StocktakeService = Depends(get_stocktake_service),
):
    return await service.start(body, user_id)


@stocktakes_router.get("/{stocktake_id}", response_model=StocktakeResponse)
async def get_stocktake(
    stocktake_id: uuid.UUID,
    _: uuid.UUID = Depends(get_current_user_id),
    service: StocktakeService = Depends(get_stocktake_service),
):
    return await service.get(stocktake_id)


@stocktakes_router.patch(
    "/{stocktake_id}/lines/{line_id}",
    response_model=StocktakeLineResponse,
)
async def update_stocktake_line(
    stocktake_id: uuid.UUID,
    line_id: uuid.UUID,
    body: StocktakeLineCountUpdate,
    _: uuid.UUID = Depends(require_receive),
    service: StocktakeService = Depends(get_stocktake_service),
):
    return await service.update_line(stocktake_id, line_id, body)


@stocktakes_router.post("/{stocktake_id}/lookup", response_model=StocktakeLineResponse)
async def lookup_stocktake_line(
    stocktake_id: uuid.UUID,
    body: StocktakeLookupRequest,
    _: uuid.UUID = Depends(require_receive),
    service: StocktakeService = Depends(get_stocktake_service),
):
    return await service.lookup(stocktake_id, body)


@stocktakes_router.post("/{stocktake_id}/complete", response_model=StocktakeResponse)
async def complete_stocktake(
    stocktake_id: uuid.UUID,
    user_id: uuid.UUID = Depends(require_receive),
    service: StocktakeService = Depends(get_stocktake_service),
):
    return await service.complete(stocktake_id, user_id)


@stocktakes_router.post("/{stocktake_id}/cancel", response_model=StocktakeResponse)
async def cancel_stocktake(
    stocktake_id: uuid.UUID,
    _: uuid.UUID = Depends(require_receive),
    service: StocktakeService = Depends(get_stocktake_service),
):
    return await service.cancel(stocktake_id)
