"""Customer access is an explicit staff approval, never a staff membership."""

from __future__ import annotations

import datetime
import hashlib
import secrets
import uuid
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from app.database import TenantSession

from app.config import settings
from app.crud.user import IdentityLookup
from app.exceptions import ForbiddenError
from app.models.customer import Customer
from app.models.customer_portal_user import CustomerPortalUser
from app.models.portal_identity import PortalAccess, PortalInvitation
from app.models.team import Team
from app.services.clerk import ClerkSession
from app.services.clerk_api import ClerkAPI, verified_primary_email
from app.services.permissions import PermissionService
from app.services.staff_identity import staff_identity_ctx
from app.services.tenant_host import require_matching_host
from f0rge_core.exceptions import (
    ConflictError,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
    ExternalServiceError,
)
from f0rge_db.crud import unit_of_work
from f0rge_db.organisation import apply_tenant_context, tenant_id_ctx, organisation_session


@dataclass(frozen=True)
class PortalPrincipal:
    portal_user_id: uuid.UUID
    access_id: uuid.UUID
    organisation_id: uuid.UUID


def invitation_status(invite: PortalInvitation) -> str:
    if invite.revoked_at:
        return "revoked"
    if invite.used_at:
        return "accepted"
    return "expired" if invite.expires_at <= datetime.datetime.utcnow() else "pending"


def invite_response(invite: PortalInvitation) -> dict:
    return {
        "id": invite.id,
        "email": invite.email,
        "expires_at": invite.expires_at,
        "status": invitation_status(invite),
    }


def access_response(access: PortalAccess, team: Team) -> dict:
    return {
        "id": access.id,
        "organisation_id": team.id,
        "organisation_name": team.name,
        "customer_id": access.customer_id,
        "customer_name": access.customer_name,
        "email": access.email,
        "status": "revoked" if access.revoked_at else "active",
        "url": (settings.public_app_url or "https://app.firstout.co.za").rstrip("/")
        + "/trade/catalogue",
    }


class PortalIdentityService:
    def __init__(self, db: AsyncSession, provider: Optional[ClerkAPI] = None) -> None:
        self.db = db
        self.provider = provider

    async def _staff_customer(self, customer_id: uuid.UUID) -> tuple[Customer, Team, uuid.UUID]:
        identity = staff_identity_ctx.get()
        if identity is None or identity.team_id != tenant_id_ctx.get():
            raise UnauthorizedError("Staff organisation required")
        if not await PermissionService(self.db).has_permission(identity.user_id, "sales.customers"):
            raise ForbiddenError("Customer access permission required")
        customer = await self.db.scalar(
            select(Customer).where(Customer.id == customer_id, Customer.team_id == identity.team_id)
        )
        if customer is None:
            raise NotFoundError("Customer not found")
        if customer.customer_type != "trade":
            raise ValidationError("Portal access is only for trade customers")
        team = await self.db.get(Team, identity.team_id)
        if team is None or team.status != "active":
            raise UnauthorizedError("Staff organisation is unavailable")
        return customer, team, identity.user_id

    async def invite(self, customer_id: uuid.UUID, email: str) -> dict:
        customer, team, actor = await self._staff_customer(customer_id)
        raw = secrets.token_urlsafe(32)
        invite = PortalInvitation(
            organisation_id=team.id,
            customer_id=customer.id,
            email=email.strip().lower(),
            token_hash=hashlib.sha256(raw.encode()).hexdigest(),
            expires_at=datetime.datetime.utcnow() + datetime.timedelta(days=7),
            invited_by_user_id=actor,
        )
        async with unit_of_work(self.db):
            self.db.add(invite)
        return {
            **invite_response(invite),
            "invitation_url": (settings.public_app_url or "https://app.firstout.co.za").rstrip("/")
            + "/trade/accept-invitation#token="
            + raw,
        }

    async def invitations(self, customer_id: uuid.UUID) -> list[dict]:
        _customer, team, _actor = await self._staff_customer(customer_id)
        rows = await self.db.scalars(
            select(PortalInvitation)
            .where(
                PortalInvitation.organisation_id == team.id,
                PortalInvitation.customer_id == customer_id,
            )
            .order_by(PortalInvitation.created_at.desc())
        )
        return [invite_response(row) for row in rows]

    async def revoke_invitation(self, customer_id: uuid.UUID, invitation_id: uuid.UUID) -> None:
        _customer, team, _actor = await self._staff_customer(customer_id)
        async with unit_of_work(self.db):
            invite = await self.db.scalar(
                select(PortalInvitation)
                .where(
                    PortalInvitation.id == invitation_id,
                    PortalInvitation.customer_id == customer_id,
                    PortalInvitation.organisation_id == team.id,
                )
                .with_for_update()
            )
            if invite is None:
                raise NotFoundError("Invitation not found")
            if invite.used_at:
                raise ConflictError("Revoke the accepted customer access instead")
            invite.revoked_at = invite.revoked_at or datetime.datetime.utcnow()

    async def staff_access(self, customer_id: uuid.UUID) -> list[dict]:
        _customer, team, _actor = await self._staff_customer(customer_id)
        rows = await self.db.scalars(
            select(PortalAccess).where(
                PortalAccess.organisation_id == team.id, PortalAccess.customer_id == customer_id
            )
        )
        return [access_response(row, team) for row in rows]

    async def revoke_access(self, customer_id: uuid.UUID, access_id: uuid.UUID) -> None:
        _customer, team, _actor = await self._staff_customer(customer_id)
        async with unit_of_work(self.db):
            access = await self.db.scalar(
                select(PortalAccess)
                .where(
                    PortalAccess.id == access_id,
                    PortalAccess.organisation_id == team.id,
                    PortalAccess.customer_id == customer_id,
                )
                .with_for_update()
            )
            if access is None:
                raise NotFoundError("Customer access not found")
            access.revoked_at = access.revoked_at or datetime.datetime.utcnow()
            portal = await self.db.scalar(
                select(CustomerPortalUser).where(
                    CustomerPortalUser.id == access.portal_user_id,
                    CustomerPortalUser.team_id == team.id,
                    CustomerPortalUser.customer_id == customer_id,
                )
            )
            if portal is not None:
                portal.is_disabled = True

    async def _global_identity(self, subject: str) -> None:
        # A disabled imported global identity remains blocked in both surfaces.
        user = await IdentityLookup(self.db).by_clerk_subject(subject)
        if user is not None and user.is_disabled:
            raise UnauthorizedError("Account is unavailable")

    async def organisations(self, identity: ClerkSession) -> list[dict]:
        await self._global_identity(identity.user_id)
        rows = await self.db.execute(
            select(PortalAccess, Team)
            .join(Team, Team.id == PortalAccess.organisation_id)
            .where(
                PortalAccess.clerk_user_id == identity.user_id,
                PortalAccess.revoked_at.is_(None),
                Team.status == "active",
            )
            .order_by(Team.name)
        )
        approved = [(access_response(access, team), access.portal_user_id) for access, team in rows]
        # Release this read-only directory transaction before borrowing another
        # connection. A one-connection pool must also support the chooser.
        await self.db.rollback()
        choices = []
        maker = async_sessionmaker(
            self.db.bind,
            expire_on_commit=False,
            sync_session_class=TenantSession,
            join_transaction_mode="create_savepoint",
        )
        for record, portal_user_id in approved:
            team_id = record["organisation_id"]
            async with organisation_session(maker, team_id) as scoped:
                customer_name = await scoped.scalar(
                    select(Customer.name)
                    .join(CustomerPortalUser, CustomerPortalUser.customer_id == Customer.id)
                    .where(
                        Customer.team_id == team_id,
                        Customer.id == record["customer_id"],
                        Customer.customer_type == "trade",
                        CustomerPortalUser.id == portal_user_id,
                        CustomerPortalUser.team_id == team_id,
                        CustomerPortalUser.is_disabled.is_(False),
                    )
                )
                if customer_name is not None:
                    choices.append({**record, "customer_name": customer_name})
        return choices

    async def accept(self, identity: ClerkSession, raw: str) -> dict:
        if self.provider is None:
            raise ExternalServiceError("Clerk identity verification is unavailable")
        email = verified_primary_email(await self.provider.user(identity.user_id))
        await self._global_identity(identity.user_id)
        async with unit_of_work(self.db):
            invite = await self.db.scalar(
                select(PortalInvitation)
                .where(PortalInvitation.token_hash == hashlib.sha256(raw.encode()).hexdigest())
                .with_for_update()
            )
            if invite is None or invitation_status(invite) != "pending":
                raise ValidationError("Invitation is invalid, expired, revoked or already used")
            if invite.email != email:
                raise ForbiddenError("Sign in with the verified email invited by the business")
            team = await self.db.get(Team, invite.organisation_id)
            if team is None or team.status != "active":
                raise ValidationError("This organisation is unavailable")
            await self.db.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),
                {"key": "portal:" + identity.user_id + ":" + str(team.id)},
            )
            await apply_tenant_context(self.db, team.id)
            tenant_id_ctx.set(team.id)
            customer = await self.db.scalar(
                select(Customer).where(
                    Customer.id == invite.customer_id,
                    Customer.team_id == team.id,
                    Customer.customer_type == "trade",
                )
            )
            if customer is None:
                raise ValidationError("This customer approval is unavailable")
            access = await self.db.scalar(
                select(PortalAccess)
                .where(
                    PortalAccess.clerk_user_id == identity.user_id,
                    PortalAccess.organisation_id == team.id,
                )
                .with_for_update()
            )
            if access is not None and (
                access.customer_id != customer.id or access.revoked_at is None
            ):
                raise ConflictError(
                    "This identity already has customer access in this organisation"
                )
            if access is None:
                existing = await self.db.scalar(
                    select(CustomerPortalUser).where(
                        CustomerPortalUser.team_id == team.id, CustomerPortalUser.email == email
                    )
                )
                if existing is not None:
                    # No adoption of an existing portal account based on email.
                    raise ConflictError(
                        "Existing portal identity requires explicit operator migration"
                    )
                portal = CustomerPortalUser(
                    team_id=team.id,
                    customer_id=customer.id,
                    email=email,
                    password_hash="!clerk-only",
                    is_disabled=False,
                )
                self.db.add(portal)
                await self.db.flush()
                access = PortalAccess(
                    clerk_user_id=identity.user_id,
                    organisation_id=team.id,
                    portal_user_id=portal.id,
                    customer_id=customer.id,
                    customer_name=customer.name,
                    email=email,
                )
                self.db.add(access)
            else:
                portal = await self.db.scalar(
                    select(CustomerPortalUser).where(
                        CustomerPortalUser.id == access.portal_user_id,
                        CustomerPortalUser.team_id == team.id,
                        CustomerPortalUser.customer_id == customer.id,
                    )
                )
                if portal is None:
                    raise ValidationError("Customer identity is unavailable")
                portal.is_disabled = False
                access.revoked_at = None
                access.email = email
            invite.used_at = datetime.datetime.utcnow()
            invite.accepted_by_clerk_user_id = identity.user_id
        return access_response(access, team)

    async def authorize(
        self, identity: ClerkSession, access_id: uuid.UUID, host_slug=None
    ) -> PortalPrincipal:
        await self._global_identity(identity.user_id)
        access = await self.db.scalar(
            select(PortalAccess).where(
                PortalAccess.id == access_id,
                PortalAccess.clerk_user_id == identity.user_id,
                PortalAccess.revoked_at.is_(None),
            )
        )
        if access is None:
            raise UnauthorizedError("Approved customer access is required")
        team = await self.db.get(Team, access.organisation_id)
        if team is None or team.status != "active":
            raise UnauthorizedError("Customer organisation is unavailable")
        require_matching_host(host_slug, team.slug)
        await apply_tenant_context(self.db, team.id)
        tenant_id_ctx.set(team.id)
        portal = await self.db.scalar(
            select(CustomerPortalUser).where(
                CustomerPortalUser.id == access.portal_user_id,
                CustomerPortalUser.team_id == team.id,
                CustomerPortalUser.customer_id == access.customer_id,
            )
        )
        if portal is None or portal.is_disabled:
            raise UnauthorizedError("Customer access is unavailable")
        customer = await self.db.scalar(
            select(Customer).where(
                Customer.id == portal.customer_id,
                Customer.team_id == team.id,
                Customer.customer_type == "trade",
            )
        )
        if customer is None:
            raise UnauthorizedError("Customer access is unavailable")
        return PortalPrincipal(portal.id, access.id, team.id)
