from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from app.dependencies.auth import (
    get_current_user_id,
    get_price_list_service,
    require_catalogue_mutate,
)
from app.schemas.price_list import (
    PriceListCreate,
    PriceListItemUpsert,
    PriceListResponse,
    PriceListUpdate,
)
from app.services.price_lists import PriceListService

price_lists_router = APIRouter(prefix="/api/v1/price-lists", tags=["price-lists"])


@price_lists_router.get("", response_model=list[PriceListResponse])
async def list_price_lists(
    _: uuid.UUID = Depends(get_current_user_id),
    service: PriceListService = Depends(get_price_list_service),
) -> list[PriceListResponse]:
    return await service.list()


@price_lists_router.post(
    "",
    response_model=PriceListResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_price_list(
    body: PriceListCreate,
    _: uuid.UUID = Depends(require_catalogue_mutate),
    service: PriceListService = Depends(get_price_list_service),
) -> PriceListResponse:
    return await service.create(body)


@price_lists_router.get("/{price_list_id}", response_model=PriceListResponse)
async def get_price_list(
    price_list_id: uuid.UUID,
    _: uuid.UUID = Depends(get_current_user_id),
    service: PriceListService = Depends(get_price_list_service),
) -> PriceListResponse:
    return await service.get(price_list_id)


@price_lists_router.patch("/{price_list_id}", response_model=PriceListResponse)
async def update_price_list(
    price_list_id: uuid.UUID,
    body: PriceListUpdate,
    _: uuid.UUID = Depends(require_catalogue_mutate),
    service: PriceListService = Depends(get_price_list_service),
) -> PriceListResponse:
    return await service.update(price_list_id, body)


@price_lists_router.delete("/{price_list_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_price_list(
    price_list_id: uuid.UUID,
    _: uuid.UUID = Depends(require_catalogue_mutate),
    service: PriceListService = Depends(get_price_list_service),
) -> None:
    await service.delete(price_list_id)


@price_lists_router.put("/{price_list_id}/items", response_model=PriceListResponse)
async def upsert_price_list_item(
    price_list_id: uuid.UUID,
    body: PriceListItemUpsert,
    _: uuid.UUID = Depends(require_catalogue_mutate),
    service: PriceListService = Depends(get_price_list_service),
) -> PriceListResponse:
    return await service.upsert_item(price_list_id, body)


@price_lists_router.delete("/{price_list_id}/items/{sku_id}", response_model=PriceListResponse)
async def delete_price_list_item(
    price_list_id: uuid.UUID,
    sku_id: uuid.UUID,
    _: uuid.UUID = Depends(require_catalogue_mutate),
    service: PriceListService = Depends(get_price_list_service),
) -> PriceListResponse:
    return await service.delete_item(price_list_id, sku_id)
