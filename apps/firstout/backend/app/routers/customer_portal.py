from __future__ import annotations


from fastapi import APIRouter, Depends, Response, status

from app.schemas.customer_portal import (
    PortalCatalogueItem,
    PortalInvitationAccept,
    PortalLoginRequest,
    PortalMeResponse,
    PortalOrderCreate,
)
from app.schemas.sales_order import SalesOrderResponse
from app.services.clerk import ClerkSession
from app.services.customer_portal import CustomerPortalService
from app.services.portal_identity import PortalIdentityService, PortalPrincipal

from app.dependencies.customer_portal import (
    get_portal_service,
    get_portal_identity_service,
    get_portal_session,
    get_portal_principal,
)

portal_router = APIRouter(prefix="/api/v1/portal", tags=["customer-portal"])


@portal_router.post("/login")
async def portal_login(
    body: PortalLoginRequest,
    response: Response,
    service: CustomerPortalService = Depends(get_portal_service),
):
    return await service.login(body, response)


@portal_router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def portal_logout(
    response: Response, service: CustomerPortalService = Depends(get_portal_service)
):
    await service.logout(response)


@portal_router.get("/organisations")
async def portal_organisations(
    identity: ClerkSession = Depends(get_portal_session),
    service: PortalIdentityService = Depends(get_portal_identity_service),
) -> list[dict]:
    return await service.organisations(identity)


@portal_router.post("/invitations/accept", status_code=201)
async def accept_portal_invitation(
    body: PortalInvitationAccept,
    identity: ClerkSession = Depends(get_portal_session),
    service: PortalIdentityService = Depends(get_portal_identity_service),
) -> dict:
    return await service.accept(identity, body.token)


@portal_router.get("/me", response_model=PortalMeResponse)
async def portal_me(
    principal: PortalPrincipal = Depends(get_portal_principal),
    service: CustomerPortalService = Depends(get_portal_service),
):
    return await service.me(principal)


@portal_router.get("/catalogue", response_model=list[PortalCatalogueItem])
async def portal_catalogue(
    principal: PortalPrincipal = Depends(get_portal_principal),
    service: CustomerPortalService = Depends(get_portal_service),
):
    return await service.catalogue(principal.portal_user_id)


@portal_router.post("/orders", response_model=SalesOrderResponse, status_code=201)
async def portal_place_order(
    body: PortalOrderCreate,
    principal: PortalPrincipal = Depends(get_portal_principal),
    service: CustomerPortalService = Depends(get_portal_service),
):
    return await service.place_order(principal.portal_user_id, body)


@portal_router.get("/orders", response_model=list[SalesOrderResponse])
async def portal_list_orders(
    principal: PortalPrincipal = Depends(get_portal_principal),
    service: CustomerPortalService = Depends(get_portal_service),
):
    return await service.list_orders(principal.portal_user_id)
