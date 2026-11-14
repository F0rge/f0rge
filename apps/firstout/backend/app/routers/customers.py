from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import (
    get_current_user_id,
    get_customers_crm_service,
    require_customers_mutate,
    require_customers_patch,
)
from app.schemas.customer_crm import (
    CustomerCrmCreate,
    CustomerCrmResponse,
    CustomerCrmUpdate,
    CustomerDuplicateMatch,
    DraftRepriceResponse,
)
from app.schemas.customer_portal import PortalMeResponse, PortalUserCreate
from app.schemas.customer_portal import PortalInvitationCreate
from app.schemas.party_archive import PartyArchiveCounts, PartyArchiveUpdate
from app.services.portal_identity import PortalIdentityService
from app.dependencies.customer_portal import get_portal_identity_service
from app.services.customer_portal import CustomerPortalService
from app.services.customers_crm import CustomersCrmService
from app.services.draft_reprice import DraftRepriceService

customers_router = APIRouter(prefix="/api/v1/customers", tags=["customers"])


@customers_router.get("", response_model=list[CustomerCrmResponse])
async def list_customers(
    overdue: Optional[bool] = None,
    active_layby: Optional[bool] = None,
    on_hold: Optional[bool] = None,
    q: Optional[str] = None,
    archived: bool = False,
    _: uuid.UUID = Depends(get_current_user_id),
    service: CustomersCrmService = Depends(get_customers_crm_service),
):
    return await service.list(
        overdue=overdue, active_layby=active_layby, on_hold=on_hold, q=q, archived=archived
    )


@customers_router.get("/archive-counts", response_model=PartyArchiveCounts)
async def customer_archive_counts(
    _: uuid.UUID = Depends(get_current_user_id),
    service: CustomersCrmService = Depends(get_customers_crm_service),
):
    return await service.archive_counts()


@customers_router.get("/duplicates", response_model=list[CustomerDuplicateMatch])
async def list_customer_duplicates(
    name: Optional[str] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    _: uuid.UUID = Depends(get_current_user_id),
    service: CustomersCrmService = Depends(get_customers_crm_service),
):
    return await service.find_duplicates(name=name, email=email, phone=phone)


@customers_router.post(
    "",
    response_model=CustomerCrmResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_customer(
    body: CustomerCrmCreate,
    _: uuid.UUID = Depends(require_customers_mutate),
    service: CustomersCrmService = Depends(get_customers_crm_service),
):
    return await service.create(body)


@customers_router.get("/{customer_id}", response_model=CustomerCrmResponse)
async def get_customer(
    customer_id: uuid.UUID,
    _: uuid.UUID = Depends(get_current_user_id),
    service: CustomersCrmService = Depends(get_customers_crm_service),
):
    return await service.get(customer_id)


@customers_router.patch("/{customer_id}", response_model=CustomerCrmResponse)
async def update_customer(
    customer_id: uuid.UUID,
    body: CustomerCrmUpdate,
    user_id: uuid.UUID = Depends(require_customers_patch),
    service: CustomersCrmService = Depends(get_customers_crm_service),
):
    return await service.update(customer_id, body, user_id)


@customers_router.patch("/{customer_id}/archive", response_model=CustomerCrmResponse)
async def archive_customer(
    customer_id: uuid.UUID,
    body: PartyArchiveUpdate,
    _: uuid.UUID = Depends(require_customers_mutate),
    service: CustomersCrmService = Depends(get_customers_crm_service),
):
    return await service.set_archived(customer_id, body.is_archived)


@customers_router.post(
    "/{customer_id}/reprice-drafts",
    response_model=DraftRepriceResponse,
)
async def reprice_customer_drafts(
    customer_id: uuid.UUID,
    _: uuid.UUID = Depends(require_customers_patch),
    db: AsyncSession = Depends(get_db),
):
    """Reprice draft quotes and draft sales orders. Issued invoices stay as they are."""
    counts = await DraftRepriceService(db).reprice(customer_id)
    return DraftRepriceResponse(quotes=counts.quotes, sales_orders=counts.sales_orders)


@customers_router.post(
    "/{customer_id}/portal-users",
    response_model=PortalMeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_customer_portal_user(
    customer_id: uuid.UUID,
    body: PortalUserCreate,
    _: uuid.UUID = Depends(require_customers_mutate),
    db: AsyncSession = Depends(get_db),
):
    return await CustomerPortalService(db).create_user(customer_id, body)


@customers_router.post("/{customer_id}/portal-invitations", status_code=201)
async def invite_customer_portal(
    customer_id: uuid.UUID,
    body: PortalInvitationCreate,
    _: uuid.UUID = Depends(require_customers_mutate),
    service: PortalIdentityService = Depends(get_portal_identity_service),
):
    return await service.invite(customer_id, str(body.email))


@customers_router.get("/{customer_id}/portal-invitations")
async def list_customer_portal_invitations(
    customer_id: uuid.UUID,
    _: uuid.UUID = Depends(require_customers_mutate),
    service: PortalIdentityService = Depends(get_portal_identity_service),
):
    return await service.invitations(customer_id)


@customers_router.delete("/{customer_id}/portal-invitations/{invitation_id}", status_code=204)
async def revoke_customer_portal_invitation(
    customer_id: uuid.UUID,
    invitation_id: uuid.UUID,
    _: uuid.UUID = Depends(require_customers_mutate),
    service: PortalIdentityService = Depends(get_portal_identity_service),
):
    await service.revoke_invitation(customer_id, invitation_id)


@customers_router.get("/{customer_id}/portal-access")
async def list_customer_portal_access(
    customer_id: uuid.UUID,
    _: uuid.UUID = Depends(require_customers_mutate),
    service: PortalIdentityService = Depends(get_portal_identity_service),
):
    return await service.staff_access(customer_id)


@customers_router.delete("/{customer_id}/portal-access/{access_id}", status_code=204)
async def revoke_customer_portal_access(
    customer_id: uuid.UUID,
    access_id: uuid.UUID,
    _: uuid.UUID = Depends(require_customers_mutate),
    service: PortalIdentityService = Depends(get_portal_identity_service),
):
    await service.revoke_access(customer_id, access_id)
