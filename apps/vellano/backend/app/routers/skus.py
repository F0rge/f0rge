from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, UploadFile, status
from fastapi.responses import Response

from app.dependencies.auth import (
    get_current_user_id,
    get_sku_bom_service,
    get_sku_service,
    require_catalogue_mutate,
)
from app.schemas.sku import SkuCreate, SkuResponse, SkuUpdate
from app.schemas.sku_bom import SkuBomLineResponse, SkuBomReplace
from app.services.sku_bom import SkuBomService
from app.services.skus import SkuService

skus_router = APIRouter(prefix="/api/v1/skus", tags=["skus"])


@skus_router.get("", response_model=list[SkuResponse])
async def list_skus(
    category: Optional[str] = None,
    _: uuid.UUID = Depends(get_current_user_id),
    service: SkuService = Depends(get_sku_service),
):
    return await service.list(category)


@skus_router.post("", response_model=SkuResponse, status_code=status.HTTP_201_CREATED)
async def create_sku(
    body: SkuCreate,
    user_id: uuid.UUID = Depends(require_catalogue_mutate),
    service: SkuService = Depends(get_sku_service),
):
    return await service.create(body, user_id)


@skus_router.get("/{sku_id}", response_model=SkuResponse)
async def get_sku(
    sku_id: uuid.UUID,
    _: uuid.UUID = Depends(get_current_user_id),
    service: SkuService = Depends(get_sku_service),
):
    return await service.get(sku_id)


@skus_router.patch("/{sku_id}", response_model=SkuResponse)
async def update_sku(
    sku_id: uuid.UUID,
    body: SkuUpdate,
    _: uuid.UUID = Depends(require_catalogue_mutate),
    service: SkuService = Depends(get_sku_service),
):
    return await service.update(sku_id, body)


@skus_router.delete("/{sku_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sku(
    sku_id: uuid.UUID,
    _: uuid.UUID = Depends(require_catalogue_mutate),
    service: SkuService = Depends(get_sku_service),
):
    return await service.delete(sku_id)


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


@skus_router.get("/{sku_id}/bom", response_model=list[SkuBomLineResponse])
async def get_sku_bom(
    sku_id: uuid.UUID,
    _: uuid.UUID = Depends(get_current_user_id),
    service: SkuBomService = Depends(get_sku_bom_service),
):
    return await service.list(sku_id)


@skus_router.put("/{sku_id}/bom", response_model=list[SkuBomLineResponse])
async def replace_sku_bom(
    sku_id: uuid.UUID,
    body: SkuBomReplace,
    _: uuid.UUID = Depends(require_catalogue_mutate),
    service: SkuBomService = Depends(get_sku_bom_service),
):
    return await service.replace(sku_id, body)
