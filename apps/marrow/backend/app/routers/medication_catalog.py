from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status

from app.dependencies.medication_catalog import get_medication_catalog_service
from app.middleware.auth import get_current_session
from app.schemas.medication_catalog import (
    MedicationCatalogItemCreate,
    MedicationCatalogItemResponse,
    MedicationCatalogItemUpdate,
)
from app.services.medication_catalog import MedicationCatalogService

router = APIRouter(
    prefix="/api/v1/medications/catalog",
    tags=["medications"],
    dependencies=[Depends(get_current_session)],
)


@router.get("", response_model=list[MedicationCatalogItemResponse])
async def list_catalog(
    include_archived: bool = Query(False),
    service: MedicationCatalogService = Depends(get_medication_catalog_service),
):
    return await service.list_items(include_archived=include_archived)


@router.post(
    "",
    response_model=MedicationCatalogItemResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_catalog_item(
    body: MedicationCatalogItemCreate,
    service: MedicationCatalogService = Depends(get_medication_catalog_service),
):
    return await service.create_item(body.key, body.label)


@router.patch("/{key}", response_model=MedicationCatalogItemResponse)
async def update_catalog_item(
    key: str,
    body: MedicationCatalogItemUpdate,
    service: MedicationCatalogService = Depends(get_medication_catalog_service),
):
    return await service.update_item(key, body.model_dump(exclude_unset=True))
