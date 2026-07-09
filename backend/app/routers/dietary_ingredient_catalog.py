from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, status

from app.dependencies.dietary_ingredient_catalog import get_dietary_ingredient_catalog_service
from app.middleware.auth import get_current_session
from app.schemas.dietary_ingredient import (
    AliasCreate,
    AliasResponse,
    DietaryIngredientCreate,
    DietaryIngredientResponse,
    DietaryIngredientUpdate,
)
from app.services.dietary_ingredient_catalog import DietaryIngredientCatalogService

router = APIRouter(
    prefix="/api/v1/dietary-ingredients",
    tags=["dietary-ingredients"],
    dependencies=[Depends(get_current_session)],
)


@router.get("", response_model=list[DietaryIngredientResponse])
async def list_ingredients(
    search: Optional[str] = Query(None),
    include_archived: bool = Query(False),
    limit: Optional[int] = Query(None, ge=1, le=200),
    service: DietaryIngredientCatalogService = Depends(get_dietary_ingredient_catalog_service),
):
    return await service.list_items(search=search, include_archived=include_archived, limit=limit)


@router.post("", response_model=DietaryIngredientResponse, status_code=status.HTTP_201_CREATED)
async def create_ingredient(
    body: DietaryIngredientCreate,
    service: DietaryIngredientCatalogService = Depends(get_dietary_ingredient_catalog_service),
):
    return await service.create_item(body)


@router.patch("/{ingredient_id}", response_model=DietaryIngredientResponse)
async def update_ingredient(
    ingredient_id: int,
    body: DietaryIngredientUpdate,
    service: DietaryIngredientCatalogService = Depends(get_dietary_ingredient_catalog_service),
):
    return await service.update_item(ingredient_id, body)


@router.post(
    "/{ingredient_id}/aliases",
    response_model=AliasResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_alias(
    ingredient_id: int,
    body: AliasCreate,
    service: DietaryIngredientCatalogService = Depends(get_dietary_ingredient_catalog_service),
):
    return await service.add_alias(ingredient_id, body)


@router.delete("/aliases/{alias_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_alias(
    alias_id: int,
    service: DietaryIngredientCatalogService = Depends(get_dietary_ingredient_catalog_service),
):
    return await service.remove_alias(alias_id)
