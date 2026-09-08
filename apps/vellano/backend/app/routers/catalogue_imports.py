from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.dependencies.auth import (
    get_catalogue_import_service,
    require_catalogue_mutate,
)
from app.schemas.catalogue_import import (
    CatalogueImportCommitResponse,
    CatalogueImportPreviewResponse,
)
from app.services.catalogue_imports import CatalogueImportService

catalogue_imports_router = APIRouter(prefix="/api/v1/imports", tags=["imports"])


@catalogue_imports_router.post("/preview", response_model=CatalogueImportPreviewResponse)
async def preview_catalogue_import(
    inventory: UploadFile = File(...),
    soh: Optional[UploadFile] = File(None),
    inventory_map: Optional[str] = Form(None),
    soh_map: Optional[str] = Form(None),
    user_id: uuid.UUID = Depends(require_catalogue_mutate),
    service: CatalogueImportService = Depends(get_catalogue_import_service),
):
    return await service.preview(inventory, soh, inventory_map, soh_map, user_id)


@catalogue_imports_router.post("/commit", response_model=CatalogueImportCommitResponse)
async def commit_catalogue_import(
    inventory: UploadFile = File(...),
    soh: Optional[UploadFile] = File(None),
    inventory_map: Optional[str] = Form(None),
    soh_map: Optional[str] = Form(None),
    user_id: uuid.UUID = Depends(require_catalogue_mutate),
    service: CatalogueImportService = Depends(get_catalogue_import_service),
):
    return await service.commit(inventory, soh, inventory_map, soh_map, user_id)
