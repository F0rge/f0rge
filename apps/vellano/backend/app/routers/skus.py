from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, UploadFile, status
from fastapi.responses import Response

from app.dependencies.auth import (
    get_current_user_id,
    get_sku_service,
    require_catalogue_mutate,
)
from app.schemas.sku import SkuCreate, SkuResponse
from app.services.skus import SkuService

skus_router = APIRouter(prefix="/api/v1/skus", tags=["skus"])


@skus_router.get("", response_model=list[SkuResponse])
async def list_skus(
    _: uuid.UUID = Depends(get_current_user_id),
    service: SkuService = Depends(get_sku_service),
):
    return await service.list()


@skus_router.post("", response_model=SkuResponse, status_code=status.HTTP_201_CREATED)
async def create_sku(
    body: SkuCreate,
    _: uuid.UUID = Depends(require_catalogue_mutate),
    service: SkuService = Depends(get_sku_service),
):
    return await service.create(body)


@skus_router.get("/{sku_id}", response_model=SkuResponse)
async def get_sku(
    sku_id: uuid.UUID,
    _: uuid.UUID = Depends(get_current_user_id),
    service: SkuService = Depends(get_sku_service),
):
    return await service.get(sku_id)


@skus_router.post("/{sku_id}/photo", response_model=SkuResponse)
async def upload_sku_photo(
    sku_id: uuid.UUID,
    photo: UploadFile = File(...),
    _: uuid.UUID = Depends(require_catalogue_mutate),
    service: SkuService = Depends(get_sku_service),
):
    return await service.upload_photo(sku_id, photo)


@skus_router.get("/{sku_id}/photo", response_model=None)
async def get_sku_photo(
    sku_id: uuid.UUID,
    _: uuid.UUID = Depends(get_current_user_id),
    service: SkuService = Depends(get_sku_service),
) -> Response:
    return await service.serve_photo(sku_id)
