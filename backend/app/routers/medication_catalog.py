from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_session
from app.schemas.medication_catalog import (
    MedicationCatalogItemCreate,
    MedicationCatalogItemResponse,
    MedicationCatalogItemUpdate,
)
from app.services import medication_catalog as medication_catalog_service

router = APIRouter(
    prefix="/api/v1/medications/catalog",
    tags=["medications"],
    dependencies=[Depends(get_current_session)],
)


@router.get("", response_model=list[MedicationCatalogItemResponse])
async def list_catalog(
    include_archived: bool = Query(False),
    db: AsyncSession = Depends(get_db),
):
    return await medication_catalog_service.list_items(db, include_archived=include_archived)


@router.post(
    "",
    response_model=MedicationCatalogItemResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_catalog_item(
    body: MedicationCatalogItemCreate,
    db: AsyncSession = Depends(get_db),
):
    return await medication_catalog_service.create_item(db, body.key, body.label)


@router.patch("/{key}", response_model=MedicationCatalogItemResponse)
async def update_catalog_item(
    key: str,
    body: MedicationCatalogItemUpdate,
    db: AsyncSession = Depends(get_db),
):
    return await medication_catalog_service.update_item(
        db, key, body.model_dump(exclude_unset=True)
    )
