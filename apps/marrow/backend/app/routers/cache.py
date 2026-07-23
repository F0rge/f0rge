from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.dependencies.cache import get_cache_warm_service
from app.middleware.auth import get_current_session
from app.services.cache_warm import CacheWarmService

router = APIRouter(
    prefix="/api/v1/cache",
    tags=["cache"],
    dependencies=[Depends(get_current_session)],
)


@router.post("/warm", status_code=status.HTTP_204_NO_CONTENT)
async def warm_cache(service: CacheWarmService = Depends(get_cache_warm_service)) -> None:
    await service.warm()
