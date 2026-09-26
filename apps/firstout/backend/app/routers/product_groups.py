from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_user_id, require_catalogue_mutate
from app.schemas.product_group import (
    ProductGroupCreate,
    ProductGroupResponse,
    ProductGroupUpdate,
    ProductGroupVariantsReplace,
)
from app.services.product_groups import ProductGroupService

router = APIRouter(prefix="/api/v1/product-groups", tags=["product-groups"])


def get_product_group_service(db: AsyncSession = Depends(get_db)) -> ProductGroupService:
    return ProductGroupService(db)


@router.get("", response_model=list[ProductGroupResponse])
async def list_product_groups(
    _: uuid.UUID = Depends(get_current_user_id),
    service: ProductGroupService = Depends(get_product_group_service),
) -> list[ProductGroupResponse]:
    return await service.list()


@router.post("", response_model=ProductGroupResponse, status_code=status.HTTP_201_CREATED)
async def create_product_group(
    body: ProductGroupCreate,
    _: uuid.UUID = Depends(require_catalogue_mutate),
    service: ProductGroupService = Depends(get_product_group_service),
) -> ProductGroupResponse:
    return await service.create(body)


@router.get("/{group_id}", response_model=ProductGroupResponse)
async def get_product_group(
    group_id: uuid.UUID,
    _: uuid.UUID = Depends(get_current_user_id),
    service: ProductGroupService = Depends(get_product_group_service),
) -> ProductGroupResponse:
    return await service.get(group_id)


@router.patch("/{group_id}", response_model=ProductGroupResponse)
async def update_product_group(
    group_id: uuid.UUID,
    body: ProductGroupUpdate,
    _: uuid.UUID = Depends(require_catalogue_mutate),
    service: ProductGroupService = Depends(get_product_group_service),
) -> ProductGroupResponse:
    return await service.update(group_id, body)


@router.put("/{group_id}/variants", response_model=ProductGroupResponse)
async def replace_product_group_variants(
    group_id: uuid.UUID,
    body: ProductGroupVariantsReplace,
    _: uuid.UUID = Depends(require_catalogue_mutate),
    service: ProductGroupService = Depends(get_product_group_service),
) -> ProductGroupResponse:
    return await service.replace_variants(group_id, body.variants)
