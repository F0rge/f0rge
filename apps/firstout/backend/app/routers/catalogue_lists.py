from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from app.dependencies.auth import get_current_user_id, require_catalogue_mutate
from app.dependencies.catalogue_lists import get_category_service, get_material_service
from app.schemas.catalogue_list import (
    CategoryCreate,
    CategoryResponse,
    CategoryTree,
    CategoryUpdate,
    Lifecycle,
    MaterialCreate,
    MaterialResponse,
    MaterialUpdate,
)
from app.services.catalogue_lists import CategoryService, MaterialService

categories_router = APIRouter(prefix="/api/v1/categories", tags=["categories"])
materials_router = APIRouter(prefix="/api/v1/materials", tags=["materials"])


@categories_router.get("", response_model=CategoryTree)
async def list_categories(
    lifecycle: Lifecycle = "active",
    _: uuid.UUID = Depends(get_current_user_id),
    service: CategoryService = Depends(get_category_service),
):
    return await service.tree(lifecycle)


@categories_router.post("", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(
    body: CategoryCreate,
    _: uuid.UUID = Depends(require_catalogue_mutate),
    service: CategoryService = Depends(get_category_service),
):
    return await service.create(body)


@categories_router.patch("/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: uuid.UUID,
    body: CategoryUpdate,
    _: uuid.UUID = Depends(require_catalogue_mutate),
    service: CategoryService = Depends(get_category_service),
):
    return await service.update(category_id, body)


@materials_router.get("", response_model=list[MaterialResponse])
async def list_materials(
    lifecycle: Lifecycle = "active",
    _: uuid.UUID = Depends(get_current_user_id),
    service: MaterialService = Depends(get_material_service),
):
    return await service.list(lifecycle)


@materials_router.post("", response_model=MaterialResponse, status_code=status.HTTP_201_CREATED)
async def create_material(
    body: MaterialCreate,
    _: uuid.UUID = Depends(require_catalogue_mutate),
    service: MaterialService = Depends(get_material_service),
):
    return await service.create(body)


@materials_router.patch("/{material_id}", response_model=MaterialResponse)
async def update_material(
    material_id: uuid.UUID,
    body: MaterialUpdate,
    _: uuid.UUID = Depends(require_catalogue_mutate),
    service: MaterialService = Depends(get_material_service),
):
    return await service.update(material_id, body)
