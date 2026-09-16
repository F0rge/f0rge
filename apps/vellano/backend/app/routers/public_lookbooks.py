from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import Response

from app.dependencies.auth import get_lookbook_service
from app.schemas.lookbook import PublicLookbookResponse
from app.services.lookbooks import LookbooksService

public_lookbooks_router = APIRouter(
    prefix="/api/v1/public/lookbooks",
    tags=["public-lookbooks"],
)


@public_lookbooks_router.get("/{token}", response_model=PublicLookbookResponse)
async def get_public_lookbook(
    token: str,
    service: LookbooksService = Depends(get_lookbook_service),
):
    return await service.public_get(token)


@public_lookbooks_router.get("/{token}/items/{item_id}/photo")
async def get_public_lookbook_photo(
    token: str,
    item_id: uuid.UUID,
    service: LookbooksService = Depends(get_lookbook_service),
) -> Response:
    return await service.serve_public_photo(token, item_id)
