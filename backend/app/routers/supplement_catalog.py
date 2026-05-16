from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_session
from app.schemas.supplement_catalog import (
    SupplementCatalogItemCreate,
    SupplementCatalogItemResponse,
    SupplementCatalogItemUpdate,
)
from app.services import supplement_catalog as supplement_catalog_service

router = APIRouter(
    prefix="/api/v1/supplements/catalog",
    tags=["supplements"],
    dependencies=[Depends(get_current_session)],
)


@router.get("", response_model=list[SupplementCatalogItemResponse])
async def list_catalog(
    include_archived: bool = Query(False),
    db: AsyncSession = Depends(get_db),
):
    return await supplement_catalog_service.list_items(
        db, include_archived=include_archived
    )


@router.post(
    "",
    response_model=SupplementCatalogItemResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_catalog_item(
    body: SupplementCatalogItemCreate,
    db: AsyncSession = Depends(get_db),
):
    return await supplement_catalog_service.create_item(db, body.key, body.label)


@router.patch("/{key}", response_model=SupplementCatalogItemResponse)
async def update_catalog_item(
    key: str,
    body: SupplementCatalogItemUpdate,
    db: AsyncSession = Depends(get_db),
):
    return await supplement_catalog_service.update_item(
        db, key, body.model_dump(exclude_unset=True)
    )
