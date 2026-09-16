from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.platform.database import get_platform_db
from app.platform.signup_service import SignupService
from app.schemas.platform_signup import (
    SignupCreateRequest,
    SignupCreateResponse,
    SignupStatusResponse,
    SignupVerifyRequest,
    SignupVerifyResponse,
    SlugAvailabilityResponse,
)

platform_signup_router = APIRouter(prefix="/api/v1/platform", tags=["platform"])


def _client_ip(request: Request) -> Optional[str]:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip() or None
    if request.client is not None:
        return request.client.host
    return None


@platform_signup_router.get("/slugs/{slug}/availability", response_model=SlugAvailabilityResponse)
async def slug_availability(
    slug: str,
    db: AsyncSession = Depends(get_platform_db),
) -> SlugAvailabilityResponse:
    return await SignupService(db).slug_availability(slug)


@platform_signup_router.post(
    "/signups",
    response_model=SignupCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_signup(
    body: SignupCreateRequest,
    request: Request,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_platform_db),
) -> SignupCreateResponse:
    return await SignupService(db).create(
        body,
        ip=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        background=background,
    )


@platform_signup_router.post("/signups/{signup_id}/resend", status_code=status.HTTP_204_NO_CONTENT)
async def resend_signup(
    signup_id: UUID,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_platform_db),
) -> None:
    await SignupService(db).resend(signup_id, background)


@platform_signup_router.post("/signups/verify", response_model=SignupVerifyResponse)
async def verify_signup(
    body: SignupVerifyRequest,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_platform_db),
) -> SignupVerifyResponse:
    return await SignupService(db).verify(body.token, background)


@platform_signup_router.get("/signups/{signup_id}/status", response_model=SignupStatusResponse)
async def signup_status(
    signup_id: UUID,
    db: AsyncSession = Depends(get_platform_db),
) -> SignupStatusResponse:
    return await SignupService(db).status(signup_id)
