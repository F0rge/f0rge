from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status

from app.dependencies.symptom_catalog import get_symptom_catalog_service
from app.middleware.auth import get_current_session
from app.schemas.symptom_catalog import (
    SymptomCatalogItemCreate,
    SymptomCatalogItemResponse,
    SymptomCatalogItemUpdate,
    SymptomOrderRequest,
)
from app.services.symptom_catalog import SymptomCatalogService

router = APIRouter(
    prefix="/api/v1/symptoms/catalog",
    tags=["symptoms"],
    dependencies=[Depends(get_current_session)],
)


@router.get("", response_model=list[SymptomCatalogItemResponse])
async def list_catalog(
    include_archived: bool = Query(False),
    service: SymptomCatalogService = Depends(get_symptom_catalog_service),
):
    return await service.list_items(include_archived=include_archived)


@router.post(
    "",
    response_model=SymptomCatalogItemResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_catalog_item(
    body: SymptomCatalogItemCreate,
    service: SymptomCatalogService = Depends(get_symptom_catalog_service),
):
    return await service.create_item(body.key, body.label)


@router.patch("/reorder", response_model=list[SymptomCatalogItemResponse])
async def reorder_catalog(
    body: SymptomOrderRequest,
    service: SymptomCatalogService = Depends(get_symptom_catalog_service),
):
    return await service.reorder_items(body.order)


@router.patch("/{key}", response_model=SymptomCatalogItemResponse)
async def update_catalog_item(
    key: str,
    body: SymptomCatalogItemUpdate,
    service: SymptomCatalogService = Depends(get_symptom_catalog_service),
):
    return await service.update_item(key, body.model_dump(exclude_unset=True))
