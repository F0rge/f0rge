from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from app.dependencies.auth import (
    get_current_user_id,
    get_lookbook_service,
    require_quotes,
)
from app.schemas.lookbook import (
    LookbookActivity,
    LookbookCreate,
    LookbookListItem,
    LookbookResponse,
)
from app.schemas.page import Page, PageParams, get_page_params
from app.services.lookbooks import LookbooksService

lookbooks_router = APIRouter(prefix="/api/v1/lookbooks", tags=["lookbooks"])


@lookbooks_router.get("", response_model=Page[LookbookListItem])
async def list_lookbooks(
    params: PageParams = Depends(get_page_params),
    _: uuid.UUID = Depends(get_current_user_id),
    service: LookbooksService = Depends(get_lookbook_service),
):
    return await service.list(params)


@lookbooks_router.post("", response_model=LookbookResponse, status_code=status.HTTP_201_CREATED)
async def create_lookbook(
    body: LookbookCreate,
    user_id: uuid.UUID = Depends(require_quotes),
    service: LookbooksService = Depends(get_lookbook_service),
):
    return await service.create(body, user_id)


@lookbooks_router.get("/{lookbook_id}/activity", response_model=LookbookActivity)
async def get_lookbook_activity(
    lookbook_id: uuid.UUID,
    _: uuid.UUID = Depends(get_current_user_id),
    service: LookbooksService = Depends(get_lookbook_service),
):
    return await service.activity(lookbook_id)


@lookbooks_router.get("/{lookbook_id}", response_model=LookbookResponse)
async def get_lookbook(
    lookbook_id: uuid.UUID,
    _: uuid.UUID = Depends(get_current_user_id),
    service: LookbooksService = Depends(get_lookbook_service),
):
    return await service.get(lookbook_id)


@lookbooks_router.post("/{lookbook_id}/revoke", response_model=LookbookResponse)
async def revoke_lookbook(
    lookbook_id: uuid.UUID,
    _: uuid.UUID = Depends(require_quotes),
    service: LookbooksService = Depends(get_lookbook_service),
):
    return await service.revoke(lookbook_id)
