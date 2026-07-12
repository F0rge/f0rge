from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.dependencies.social import get_social_service
from app.middleware.auth import get_current_session
from app.schemas.social import HandleAvailableResponse, PublicUserCard
from app.services.social import SocialService

router = APIRouter(
    prefix="/api/v1/social",
    tags=["social"],
)


@router.get("/handle-available", response_model=HandleAvailableResponse)
async def handle_available(
    handle: str = Query(..., min_length=1),
    service: SocialService = Depends(get_social_service),
):
    available = await service.check_handle_available(handle)
    return HandleAvailableResponse(available=available)


@router.get(
    "/users/lookup",
    response_model=PublicUserCard,
    dependencies=[Depends(get_current_session)],
)
async def lookup_user(
    handle: str = Query(..., min_length=1),
    service: SocialService = Depends(get_social_service),
):
    return await service.lookup_by_handle(handle)
