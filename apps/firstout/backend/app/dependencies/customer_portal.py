from __future__ import annotations

import uuid
from typing import Optional

from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.tenant_signup import get_clerk_api
from app.middleware.auth import _bearer_token
from app.services.clerk import ClerkSession, verify_clerk_session
from app.services.clerk_api import ClerkAPI
from app.services.customer_portal import CustomerPortalService
from app.services.portal_identity import PortalIdentityService, PortalPrincipal
from app.services.tenant_host import request_tenant_slug
from f0rge_core.exceptions import UnauthorizedError


def get_portal_service(db: AsyncSession = Depends(get_db)) -> CustomerPortalService:
    return CustomerPortalService(db)


def get_portal_identity_service(
    db: AsyncSession = Depends(get_db), provider: ClerkAPI = Depends(get_clerk_api)
) -> PortalIdentityService:
    return PortalIdentityService(db, provider)


async def get_portal_session(
    authorization: Optional[str] = Header(default=None, include_in_schema=False),
) -> ClerkSession:
    token = _bearer_token(authorization)
    if not token:
        raise UnauthorizedError("A Clerk customer sign-in is required")
    return await verify_clerk_session(token, require_active=True)


async def get_portal_principal(
    request: Request,
    identity: ClerkSession = Depends(get_portal_session),
    access_id: Optional[uuid.UUID] = Header(default=None, alias="X-Firstout-Portal-Access"),
    service: PortalIdentityService = Depends(get_portal_identity_service),
) -> PortalPrincipal:
    if access_id is None:
        raise UnauthorizedError("Select approved customer access")
    return await service.authorize(identity, access_id, request_tenant_slug(request))
