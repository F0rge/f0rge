from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query

from app.dependencies.auth import get_current_user_id, get_search_service
from app.schemas.search import SearchResponse
from app.services.search import SearchService

search_router = APIRouter(prefix="/api/v1/search", tags=["search"])


@search_router.get("", response_model=SearchResponse)
async def search(
    q: str = Query(..., min_length=1),
    _: uuid.UUID = Depends(get_current_user_id),
    service: SearchService = Depends(get_search_service),
) -> SearchResponse:
    return await service.search(q)
