from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends

from app.dependencies.auth import (
    get_category_map_service,
    get_current_user_id,
    require_books_mutate,
)
from app.schemas.category_account_map import CategoryAccountMapResponse, CategoryAccountMapUpsert
from app.services.category_maps import CategoryMapService

category_maps_router = APIRouter(prefix="/api/v1/category-maps", tags=["category-maps"])


@category_maps_router.get("", response_model=list[CategoryAccountMapResponse])
async def list_category_maps(
    _: uuid.UUID = Depends(get_current_user_id),
    service: CategoryMapService = Depends(get_category_map_service),
):
    return await service.list()


@category_maps_router.put("", response_model=CategoryAccountMapResponse)
async def upsert_category_map(
    body: CategoryAccountMapUpsert,
    _: uuid.UUID = Depends(require_books_mutate),
    service: CategoryMapService = Depends(get_category_map_service),
):
    return await service.upsert(body)
