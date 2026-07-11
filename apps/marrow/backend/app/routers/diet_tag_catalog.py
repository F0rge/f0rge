from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status

from app.dependencies.diet_tag_catalog import get_diet_tag_catalog_service
from app.middleware.auth import get_current_session
from app.schemas.diet_tag_catalog import (
    DietTagCatalogItemCreate,
    DietTagCatalogItemResponse,
    DietTagCatalogItemUpdate,
)
from app.services.diet_tag_catalog import DietTagCatalogService

router = APIRouter(
    prefix="/api/v1/diet-tags/catalog",
    tags=["diet-tags"],
    dependencies=[Depends(get_current_session)],
)


@router.get("", response_model=list[DietTagCatalogItemResponse])
async def list_catalog(
    include_archived: bool = Query(False),
    service: DietTagCatalogService = Depends(get_diet_tag_catalog_service),
):
    return await service.list_items(include_archived=include_archived)


@router.post(
    "",
    response_model=DietTagCatalogItemResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_catalog_item(
    body: DietTagCatalogItemCreate,
    service: DietTagCatalogService = Depends(get_diet_tag_catalog_service),
):
    return await service.create_item(body.key, body.label)


@router.patch("/{key}", response_model=DietTagCatalogItemResponse)
async def update_catalog_item(
    key: str,
    body: DietTagCatalogItemUpdate,
    service: DietTagCatalogService = Depends(get_diet_tag_catalog_service),
):
    return await service.update_item(key, body.model_dump(exclude_unset=True))
