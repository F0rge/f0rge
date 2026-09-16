from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Cookie, Depends, HTTPException, status
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
from app.services.auth import token_tenant_id
from app.services.customer_portal import (
    CUSTOMER_COOKIE_NAME,
    CustomerPortalService,
    decode_customer_access_token,
)
from app.tenancy.context import tenant_ctx
from sqlalchemy.ext.asyncio import AsyncSession

portal_router = APIRouter(prefix="/api/v1/portal", tags=["customer-portal"])


def get_portal_service(db: AsyncSession = Depends(get_db)) -> CustomerPortalService:
    return CustomerPortalService(db)


async def get_current_portal_user_id(
    vellano_customer_session: Optional[str] = Cookie(default=None, alias=CUSTOMER_COOKIE_NAME),
) -> uuid.UUID:
    if not vellano_customer_session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        user_id = decode_customer_access_token(vellano_customer_session)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")
    ctx = tenant_ctx.get()
    if ctx is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="tenant_not_found")
    if token_tenant_id(vellano_customer_session) != ctx.id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")
    return user_id


@portal_router.post("/login", response_model=PortalLoginResponse)
async def portal_login(
    body: PortalLoginRequest,
    response: Response,
    service: CustomerPortalService = Depends(get_portal_service),
):
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
