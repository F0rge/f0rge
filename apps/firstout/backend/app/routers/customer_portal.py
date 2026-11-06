from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, status
import jwt
from sqlalchemy import select
from app.models.team import Team
from app.services.auth import _require_jwt_secret
from app.services.tenant_host import request_tenant_slug, require_matching_host
from f0rge_db.organisation import apply_tenant_context, tenant_id_ctx
from fastapi.responses import Response

from app.database import get_db
from app.schemas.customer_portal import (
    PortalCatalogueItem,
    PortalLoginRequest,
    PortalLoginResponse,
    PortalMeResponse,
    PortalOrderCreate,
)
from app.schemas.sales_order import SalesOrderResponse
from app.services.customer_portal import (
    CUSTOMER_COOKIE_NAME,
    CustomerPortalService,
    decode_customer_access_token,
)
from sqlalchemy.ext.asyncio import AsyncSession

portal_router = APIRouter(prefix="/api/v1/portal", tags=["customer-portal"])


def get_portal_service(db: AsyncSession = Depends(get_db)) -> CustomerPortalService:
    return CustomerPortalService(db)


async def get_current_portal_user_id(
    request: Request,
    db: AsyncSession = Depends(get_db),
    firstout_customer_session: Optional[str] = Cookie(default=None, alias=CUSTOMER_COOKIE_NAME),
) -> uuid.UUID:
    if not firstout_customer_session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        user_id = decode_customer_access_token(firstout_customer_session)
        claims = jwt.decode(firstout_customer_session, _require_jwt_secret(), algorithms=["HS256"])
        team_id = claims.get("team_id")
        query = (
            select(Team).where(Team.id == uuid.UUID(team_id))
            if team_id
            else select(Team).where(Team.slug == "firstout")
        )
        team = (await db.execute(query)).scalar_one_or_none()
        if team is None or team.status != "active":
            raise HTTPException(401, "Invalid session")
        require_matching_host(request_tenant_slug(request), team.slug)
        await apply_tenant_context(db, team.id)
        tenant_id_ctx.set(team.id)
        return user_id
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")


@portal_router.post("/login", response_model=PortalLoginResponse)
async def portal_login(
    body: PortalLoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    service: CustomerPortalService = Depends(get_portal_service),
):
    slug = request_tenant_slug(request) or "firstout"
    team = (
        await db.execute(select(Team).where(Team.slug == slug, Team.status == "active"))
    ).scalar_one_or_none()
    if team is None:
        raise HTTPException(404, "Unknown tenant")
    await apply_tenant_context(db, team.id)
    tenant_id_ctx.set(team.id)
    return await service.login(body, response)


@portal_router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def portal_logout(
    response: Response,
    service: CustomerPortalService = Depends(get_portal_service),
):
    await service.logout(response)


@portal_router.get("/me", response_model=PortalMeResponse)
async def portal_me(
    portal_user_id: uuid.UUID = Depends(get_current_portal_user_id),
    service: CustomerPortalService = Depends(get_portal_service),
):
    return await service.me(portal_user_id)


@portal_router.get("/catalogue", response_model=list[PortalCatalogueItem])
async def portal_catalogue(
    portal_user_id: uuid.UUID = Depends(get_current_portal_user_id),
    service: CustomerPortalService = Depends(get_portal_service),
):
    return await service.catalogue(portal_user_id)


@portal_router.post(
    "/orders",
    response_model=SalesOrderResponse,
    status_code=status.HTTP_201_CREATED,
)
async def portal_place_order(
    body: PortalOrderCreate,
    portal_user_id: uuid.UUID = Depends(get_current_portal_user_id),
    service: CustomerPortalService = Depends(get_portal_service),
):
    return await service.place_order(portal_user_id, body)


@portal_router.get("/orders", response_model=list[SalesOrderResponse])
async def portal_list_orders(
    portal_user_id: uuid.UUID = Depends(get_current_portal_user_id),
    service: CustomerPortalService = Depends(get_portal_service),
):
    return await service.list_orders(portal_user_id)
