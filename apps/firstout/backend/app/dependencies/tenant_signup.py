from __future__ import annotations

from typing import AsyncIterator, Optional

import httpx
from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.services.clerk import ClerkSession, verify_clerk_session
from app.services.clerk_api import ClerkAPI
from app.services.tenant_host import request_tenant_slug
from app.services.tenant_signup import OrganisationService, TenantSignupService
from app.services.clerk_webhooks import ClerkWebhookService
from f0rge_core.exceptions import UnauthorizedError


async def get_clerk_api() -> AsyncIterator[ClerkAPI]:
    async with httpx.AsyncClient() as client:
        yield ClerkAPI(client, settings.clerk_secret_key)


async def get_signup_identity(
    request: Request,
    authorization: Optional[str] = Header(default=None, include_in_schema=False),
) -> ClerkSession:
    if request_tenant_slug(request) is not None:
        raise UnauthorizedError("Open the main application to create or join an organisation")
    scheme, _separator, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token or any(char.isspace() for char in token):
        raise UnauthorizedError("A Clerk sign-in is required")
    return await verify_clerk_session(token, require_active=True)


def get_tenant_signup_service(
    db: AsyncSession = Depends(get_db), provider: ClerkAPI = Depends(get_clerk_api)
) -> TenantSignupService:
    return TenantSignupService(db, provider)


def get_organisation_service(
    db: AsyncSession = Depends(get_db), provider: ClerkAPI = Depends(get_clerk_api)
) -> OrganisationService:
    return OrganisationService(db, provider)


def get_clerk_webhook_service(
    db: AsyncSession = Depends(get_db), provider: ClerkAPI = Depends(get_clerk_api)
) -> ClerkWebhookService:
    return ClerkWebhookService(db, provider)
