from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Literal, Optional, Union

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import UploadFile as ParsedUploadFile
from starlette.formparsers import MultiPartException, MultiPartParser

from app.database import get_db
from app.dependencies.auth import (
    get_current_user_id,
    get_sku_bom_service,
    get_sku_service,
    require_catalogue_mutate,
    require_owner,
)
from app.schemas.curated_catalogue import CuratedCatalogueResult
from app.schemas.sku import (
    SKU_SETTING_PHOTO_SLOT,
    SkuCreate,
    SkuListPage,
    SkuResponse,
    SkuUnitCostPage,
    SkuUpdate,
)
from app.schemas.sku_bom import SkuBomLineResponse, SkuBomReplace
from app.services.sku_bom import SkuBomService
from app.services.curated_catalogue import CuratedCatalogueService
from app.services.curated_catalogue_archive import MAX_ARCHIVE_BYTES
from app.services.skus import SkuService
from f0rge_core.exceptions import ValidationError

skus_router = APIRouter(prefix="/api/v1/skus", tags=["skus"])


@skus_router.get("", response_model=Union[list[SkuResponse], SkuListPage])
async def list_skus(
    category: Optional[str] = None,
    limit: Optional[int] = Query(default=None, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    q: Optional[str] = None,
    preferred_supplier_id: Optional[uuid.UUID] = None,
    lifecycle: Literal["active", "archived", "all"] = "active",
    user_id: uuid.UUID = Depends(get_current_user_id),
    service: SkuService = Depends(get_sku_service),
):
    return await service.list(
        category,
        user_id,
        limit=limit,
        offset=offset,
        q=q,
        preferred_supplier_id=preferred_supplier_id,
        lifecycle=lifecycle,
    )


@skus_router.get("/unit-costs", response_model=SkuUnitCostPage)
async def list_sku_unit_costs(
    category: Optional[str] = None,
    limit: Optional[int] = Query(default=None, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    q: Optional[str] = None,
    preferred_supplier_id: Optional[uuid.UUID] = None,
    lifecycle: Literal["active", "archived", "all"] = "active",
    user_id: uuid.UUID = Depends(get_current_user_id),
    service: SkuService = Depends(get_sku_service),
):
    return await service.list_unit_costs(
        user_id,
        category=category,
        q=q,
        preferred_supplier_id=preferred_supplier_id,
        lifecycle=lifecycle,
        limit=limit,
        offset=offset,
    )


@skus_router.post("", response_model=SkuResponse, status_code=status.HTTP_201_CREATED)
async def create_sku(
    body: SkuCreate,
    user_id: uuid.UUID = Depends(require_catalogue_mutate),
    service: SkuService = Depends(get_sku_service),
):
    return await service.create(body, user_id)


@skus_router.post(
    "/curated-catalogue",
    response_model=CuratedCatalogueResult,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "required": ["archive"],
                        "properties": {
                            "archive": {"type": "string", "format": "binary"},
                            "dry_run": {"type": "boolean", "default": True},
                            "scope": {
                                "type": "string",
                                "enum": ["catalogue", "sku"],
                                "default": "catalogue",
                            },
                        },
                    }
                }
            },
        }
    },
)
async def import_curated_catalogue(
    request: Request,
    user_id: uuid.UUID = Depends(require_owner),
    db: AsyncSession = Depends(get_db),
) -> CuratedCatalogueResult:
    if request.headers.get("content-type", "").split(";", 1)[0].strip() != "multipart/form-data":
        raise ValidationError("A catalogue ZIP upload is required")

    async def upload_chunks() -> AsyncIterator[bytes]:
        received = 0
        async for chunk in request.stream():
            received += len(chunk)
            if received > MAX_ARCHIVE_BYTES + 1024 * 1024:
                raise MultiPartException("The catalogue upload exceeds 41 MiB")
            yield chunk

    try:
        form = await MultiPartParser(
            request.headers, upload_chunks(), max_files=1, max_fields=2, max_part_size=1024
        ).parse()
    except MultiPartException as exc:
        raise ValidationError(exc.message) from exc
    try:
        archive = form.get("archive")
        dry_run = form.get("dry_run", "true")
        scope = form.get("scope", "catalogue")
        if not isinstance(archive, ParsedUploadFile) or dry_run not in ("true", "false"):
            raise ValidationError("Provide an archive file and a true or false dry_run value")
        if scope != "catalogue" and scope != "sku":
            raise ValidationError("Specify catalogue or sku as the import scope")
        return await CuratedCatalogueService(db).import_archive(
            archive.file, user_id=user_id, dry_run=dry_run == "true", scope=scope
        )
    finally:
        await form.close()


@skus_router.get("/{sku_id}", response_model=SkuResponse)
async def get_sku(
    sku_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    service: SkuService = Depends(get_sku_service),
):
    return await service.get(sku_id, user_id)


@skus_router.patch("/{sku_id}", response_model=SkuResponse)
async def update_sku(
    sku_id: uuid.UUID,
    body: SkuUpdate,
    user_id: uuid.UUID = Depends(require_catalogue_mutate),
    service: SkuService = Depends(get_sku_service),
):
    return await service.update(sku_id, body, user_id)


@skus_router.delete("/{sku_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sku(
    sku_id: uuid.UUID,
    _: uuid.UUID = Depends(require_catalogue_mutate),
    service: SkuService = Depends(get_sku_service),
):
    return await service.delete(sku_id)


@skus_router.post("/{sku_id}/photo", response_model=SkuResponse)
async def upload_sku_photo(
    sku_id: uuid.UUID,
    photo: UploadFile = File(...),
    user_id: uuid.UUID = Depends(require_catalogue_mutate),
    service: SkuService = Depends(get_sku_service),
):
    return await service.upload_photo(sku_id, photo, user_id)


@skus_router.get("/{sku_id}/photo", response_model=None)
async def get_sku_photo(
    sku_id: uuid.UUID,
    slot: int = Query(default=1, ge=1, le=SKU_SETTING_PHOTO_SLOT),
    _: uuid.UUID = Depends(get_current_user_id),
    service: SkuService = Depends(get_sku_service),
) -> Response:
    return await service.serve_photo(sku_id, slot=slot)


@skus_router.get("/{sku_id}/bom", response_model=list[SkuBomLineResponse])
async def get_sku_bom(
    sku_id: uuid.UUID,
    _: uuid.UUID = Depends(get_current_user_id),
    service: SkuBomService = Depends(get_sku_bom_service),
):
    return await service.list(sku_id)


@skus_router.put("/{sku_id}/bom", response_model=list[SkuBomLineResponse])
async def replace_sku_bom(
    sku_id: uuid.UUID,
    body: SkuBomReplace,
    _: uuid.UUID = Depends(require_catalogue_mutate),
    service: SkuBomService = Depends(get_sku_bom_service),
):
    return await service.replace(sku_id, body)
