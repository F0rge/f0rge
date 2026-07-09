from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status

from app.dependencies.supplement_catalog import get_supplement_catalog_service
from app.middleware.auth import get_current_session
from app.schemas.supplement_catalog import (
    SupplementCatalogItemCreate,
    SupplementCatalogItemResponse,
    SupplementCatalogItemUpdate,
)
from app.services.supplement_catalog import SupplementCatalogService

router = APIRouter(
    prefix="/api/v1/supplements/catalog",
    tags=["supplements"],
    dependencies=[Depends(get_current_session)],
)


@router.get("", response_model=list[SupplementCatalogItemResponse])
async def list_catalog(
    include_archived: bool = Query(False),
    service: SupplementCatalogService = Depends(get_supplement_catalog_service),
):
    return await service.list_items(include_archived=include_archived)


@router.post(
    "",
    response_model=SupplementCatalogItemResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_catalog_item(
    body: SupplementCatalogItemCreate,
    service: SupplementCatalogService = Depends(get_supplement_catalog_service),
):
    return await service.create_item(body.key, body.label)


@router.patch("/{key}", response_model=SupplementCatalogItemResponse)
async def update_catalog_item(
    key: str,
    body: SupplementCatalogItemUpdate,
    service: SupplementCatalogService = Depends(get_supplement_catalog_service),
):
    return await service.update_item(key, body.model_dump(exclude_unset=True))
