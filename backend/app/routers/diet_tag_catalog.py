from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_session
from app.schemas.diet_tag_catalog import (
    DietTagCatalogItemCreate,
    DietTagCatalogItemResponse,
    DietTagCatalogItemUpdate,
)
from app.services import diet_tag_catalog as diet_tag_catalog_service

router = APIRouter(
    prefix="/api/v1/diet-tags/catalog",
    tags=["diet-tags"],
    dependencies=[Depends(get_current_session)],
)


@router.get("", response_model=list[DietTagCatalogItemResponse])
async def list_catalog(
    include_archived: bool = Query(False),
    db: AsyncSession = Depends(get_db),
):
    return await diet_tag_catalog_service.list_items(db, include_archived=include_archived)


@router.post(
    "",
    response_model=DietTagCatalogItemResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_catalog_item(
    body: DietTagCatalogItemCreate,
    db: AsyncSession = Depends(get_db),
):
    return await diet_tag_catalog_service.create_item(db, body.key, body.label)


@router.patch("/{key}", response_model=DietTagCatalogItemResponse)
async def update_catalog_item(
    key: str,
    body: DietTagCatalogItemUpdate,
    db: AsyncSession = Depends(get_db),
):
    return await diet_tag_catalog_service.update_item(db, key, body.model_dump(exclude_unset=True))
