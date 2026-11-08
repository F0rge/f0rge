from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Response

from app.dependencies.tenant_signup import (
    get_organisation_service,
    get_signup_identity,
    get_tenant_signup_service,
)
from app.middleware.auth import get_current_user_id
from app.schemas.tenant_signup import OrganisationInvitationCreate, SignupIntent
from app.services.clerk import ClerkSession
from app.services.tenant_signup import OrganisationService, TenantSignupService, signup_status

router = APIRouter(prefix="/api/v1/tenant-signup", tags=["tenant-signup"])
organisations_router = APIRouter(prefix="/api/v1/organisations/current", tags=["organisations"])


@router.get("/status")
async def status() -> dict:
    return signup_status()


@router.post("/preview")
async def preview(
    body: SignupIntent, service: TenantSignupService = Depends(get_tenant_signup_service)
) -> dict:
    return await service.preview(body)


@router.get("/me")
async def me(
    identity: ClerkSession = Depends(get_signup_identity),
    service: TenantSignupService = Depends(get_tenant_signup_service),
) -> dict:
    return await service.me(identity)


@router.post("", status_code=201)
async def create(
    body: SignupIntent,
    identity: ClerkSession = Depends(get_signup_identity),
    service: TenantSignupService = Depends(get_tenant_signup_service),
) -> dict:
    return await service.create(identity, body)


@organisations_router.get("")
async def current(
    _user: uuid.UUID = Depends(get_current_user_id),
    service: OrganisationService = Depends(get_organisation_service),
) -> dict:
    return await service.current()


@organisations_router.get("/invitations")
async def invitations(
    _user: uuid.UUID = Depends(get_current_user_id),
    service: OrganisationService = Depends(get_organisation_service),
) -> list[dict]:
    return await service.invitations()


@organisations_router.post("/invitations", status_code=201)
async def invite(
    body: OrganisationInvitationCreate,
    _user: uuid.UUID = Depends(get_current_user_id),
    service: OrganisationService = Depends(get_organisation_service),
) -> dict:
    return await service.invite(body)


@organisations_router.delete("/invitations/{invitation_id}", status_code=204)
async def revoke(
    invitation_id: uuid.UUID,
    _user: uuid.UUID = Depends(get_current_user_id),
    service: OrganisationService = Depends(get_organisation_service),
) -> Response:
    await service.revoke(invitation_id)
    return Response(status_code=204)
