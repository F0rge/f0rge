"""Verified identity onboarding; tenant data is inaccessible until membership exists."""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Optional

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.customer import Customer
from app.models.location import Location, LocationType
from app.models.location_bin import new_floor_bin
from app.models.membership import Membership
from app.models.role import Role, RolePermission
from app.models.team import Team
from app.models.team_settings import TeamSettings
from app.models.tenant_onboarding import TenantInvitation, TenantProvisioningAttempt
from app.models.user import User
from app.permissions import ROLE_PRESETS, ROLE_PRESET_NAMES
from app.schemas.tenant_signup import OrganisationInvitationCreate, SignupIntent
from app.services.clerk import ClerkSession
from app.services.clerk_api import ClerkAPI, MAX_MEMBERS, verified_primary_email
from app.services.document_numbering import DocumentNumberingService
from app.services.staff_identity import staff_identity_ctx
from f0rge_core.exceptions import ConflictError, NotFoundError, UnauthorizedError, ValidationError
from f0rge_db.crud import unit_of_work
from f0rge_db.organisation import apply_tenant_context, tenant_id_ctx


def organisation_url() -> str:
    return (settings.public_app_url or "https://app.firstout.co.za").rstrip("/") + "/"


def signup_status() -> dict:
    return {
        "enabled": settings.tenant_signup_enabled
        and settings.tenant_isolation_mode == "enforced"
        and settings.clerk_enabled,
        "billing_disabled": settings.billing_disabled,
        "billing_test_mode": settings.billing_test_mode,
        "mode": "self-service",
        "max_members": MAX_MEMBERS,
    }


def require_signup() -> None:
    if not signup_status()["enabled"]:
        raise ValidationError("Organisation signup is not enabled")
    if not settings.billing_disabled:
        raise ValidationError("Paid signup is not supported")


def organisation_response(team: Team, role: str) -> dict:
    return {
        "id": team.id,
        "name": team.name,
        "slug": team.slug,
        "clerk_org_id": team.clerk_org_id,
        "role": role,
        "url": organisation_url(),
    }


class TenantSignupService:
    def __init__(self, db: AsyncSession, provider: ClerkAPI) -> None:
        self.db = db
        self.provider = provider

    async def preview(self, data: SignupIntent) -> dict:
        require_signup()
        return {"name": data.name, "slug": data.slug, "billing": "disabled", "provisioned": False}

    async def me(self, identity: ClerkSession) -> dict:
        require_signup()
        profile = await self.provider.user(identity.user_id)
        email = verified_primary_email(profile)
        await self.reconcile_invitations(identity.user_id, profile)
        user = await self.db.scalar(select(User).where(User.clerk_user_id == identity.user_id))
        organisations = []
        if user is not None:
            if user.is_disabled:
                raise UnauthorizedError("Account is disabled")
            rows = (
                await self.db.execute(
                    select(Team, Membership)
                    .join(Membership, Team.id == Membership.team_id)
                    .where(
                        Membership.user_id == user.id,
                        Membership.is_disabled.is_(False),
                        Team.status == "active",
                    )
                )
            ).all()
            organisations = [
                organisation_response(
                    team, user.role if membership.is_legacy_home else membership.role
                )
                for team, membership in rows
            ]
        return {
            "clerk_user_id": identity.user_id,
            "email": email,
            "display_name": profile_name(profile),
            "organisations": organisations,
        }

    async def create(self, identity: ClerkSession, data: SignupIntent) -> dict:
        require_signup()
        profile = await self.provider.user(identity.user_id)
        email = verified_primary_email(profile)
        existing_user = await self._identity(identity.user_id, email)
        attempt = await self._reserve(identity.user_id, data)
        if attempt.result_team_id:
            team = await self.db.get(Team, attempt.result_team_id)
            return organisation_response(team, "owner")
        # Persist the external organisation ID separately. If the response/commit is
        # lost, Clerk's private operation marker recovers only this exact attempt.
        async with unit_of_work(self.db):
            attempt = await self.db.scalar(
                select(TenantProvisioningAttempt)
                .where(TenantProvisioningAttempt.id == attempt.id)
                .with_for_update()
            )
            if not attempt.clerk_org_id:
                attempt.clerk_org_id = await self.provider.ensure_organisation(
                    name=data.name,
                    slug=data.slug,
                    created_by=identity.user_id,
                    operation_id=str(attempt.id),
                )
        async with unit_of_work(self.db):
            attempt = await self.db.scalar(
                select(TenantProvisioningAttempt)
                .where(TenantProvisioningAttempt.id == attempt.id)
                .with_for_update()
            )
            if attempt.result_team_id:
                team = await self.db.get(Team, attempt.result_team_id)
                return organisation_response(team, "owner")
            # Serialize all new directory identities for this verified subject.
            await self.db.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),
                {"key": "clerk-user:" + identity.user_id},
            )
            existing_user = await self._identity(identity.user_id, email)
            team = Team(
                name=data.name, slug=data.slug, clerk_org_id=attempt.clerk_org_id, status="active"
            )
            self.db.add(team)
            await self.db.flush()
            await apply_tenant_context(self.db, team.id)
            token = tenant_id_ctx.set(team.id)
            try:
                location = Location(
                    team_id=team.id, name=data.location_name, type=LocationType.SHOWROOM
                )
                self.db.add(location)
                await self.db.flush()
                self.db.add(new_floor_bin(location.id))
                user = existing_user
                if user is None:
                    user = User(
                        team_id=team.id,
                        email=email,
                        clerk_user_id=identity.user_id,
                        password_hash="!clerk-only",
                        display_name=profile_name(profile),
                        role="owner",
                        default_location_id=location.id,
                        is_disabled=False,
                    )
                    self.db.add(user)
                    await self.db.flush()
                self.db.add(
                    Membership(
                        team_id=team.id,
                        user_id=user.id,
                        role="owner",
                        permission_source="clerk",
                        is_legacy_home=False,
                        is_disabled=False,
                        default_location_id=location.id,
                    )
                )
                for slug, keys in ROLE_PRESETS.items():
                    self.db.add(
                        Role(
                            team_id=team.id,
                            slug=slug,
                            name=ROLE_PRESET_NAMES[slug],
                            is_system=True,
                            is_owner_preset=slug == "owner",
                            permissions=[
                                RolePermission(team_id=team.id, key=key) for key in sorted(keys)
                            ],
                        )
                    )
                self.db.add(
                    TeamSettings(
                        team_id=team.id,
                        legal_name=data.legal_name or data.name,
                        address=data.address,
                        vat_number=data.vat_number,
                        default_till_location_id=location.id,
                    )
                )
                await self._bootstrap_accounts()
                await DocumentNumberingService(self.db).ensure_all_for_team(team.id)
                self.db.add(Customer(team_id=team.id, name="Walk-in customer"))
                attempt.result_team_id = team.id
                await self.db.flush()
            finally:
                tenant_id_ctx.reset(token)
        return organisation_response(team, "owner")

    async def _reserve(self, subject: str, data: SignupIntent) -> TenantProvisioningAttempt:
        digest = hashlib.sha256(json.dumps(data.model_dump(), sort_keys=True).encode()).hexdigest()
        async with unit_of_work(self.db):
            await self.db.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),
                {"key": "tenant-signup:" + subject},
            )
            await self.db.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),
                {"key": "tenant-signup-slug:" + data.slug},
            )
            attempt = await self.db.scalar(
                select(TenantProvisioningAttempt)
                .where(TenantProvisioningAttempt.slug == data.slug)
                .with_for_update()
            )
            if attempt:
                if attempt.clerk_user_id != subject or attempt.payload_digest != digest:
                    raise ConflictError("Business URL is reserved by another signup request")
                return attempt
            if await self.db.scalar(select(Team.id).where(Team.slug == data.slug)):
                raise ConflictError("Business URL is already in use")
            count = await self.db.scalar(
                select(func.count())
                .select_from(TenantProvisioningAttempt)
                .where(TenantProvisioningAttempt.clerk_user_id == subject)
            )
            if count >= 3:
                raise ValidationError("You may create up to three organisations")
            attempt = TenantProvisioningAttempt(
                clerk_user_id=subject, slug=data.slug, payload_digest=digest
            )
            self.db.add(attempt)
            await self.db.flush()
        return attempt

    async def _identity(self, subject: str, email: str) -> Optional[User]:
        user = await self.db.scalar(select(User).where(User.clerk_user_id == subject))
        if user is not None:
            if user.is_disabled:
                raise UnauthorizedError("Account is disabled")
            return user
        if await self.db.scalar(select(User.id).where(func.lower(User.email) == email.lower())):
            raise ConflictError(
                "This email has an existing staff account. Sign in with your existing login; an administrator must link it explicitly."
            )
        return None

    async def _bootstrap_accounts(self) -> None:
        from app.services.chart_of_accounts import (
            BANK_ACCOUNT_SEEDS,
            CATEGORY_ACCOUNTS,
            CATEGORY_MAPS,
            CHART_OF_ACCOUNTS,
            CODE_BANK,
            CODE_OPENING,
            CODE_DEPOSITS,
            AccountType,
            CategoryAccountMap,
            ChartOfAccountsSeedService,
        )

        records = {
            code: (name, kind) for code, name, kind in (*CHART_OF_ACCOUNTS, *CATEGORY_ACCOUNTS)
        }
        records[CODE_OPENING] = ("Opening balances", AccountType.EQUITY)
        records[CODE_DEPOSITS] = ("Customer deposits", AccountType.LIABILITY)
        records.update({code: (name, AccountType.ASSET) for code, name in BANK_ACCOUNT_SEEDS})
        bank_codes = {CODE_BANK, *(code for code, _name in BANK_ACCOUNT_SEEDS)}
        for code, (name, kind) in records.items():
            self.db.add(
                ChartOfAccountsSeedService._system_account(
                    code, name, kind, is_bank=code in bank_codes
                )
            )
        await self.db.flush()
        for category, sales, cogs, adjustments, count_var in CATEGORY_MAPS:
            self.db.add(
                CategoryAccountMap(
                    category=category,
                    sales_code=sales,
                    cogs_code=cogs,
                    stock_adj_code=adjustments,
                    count_var_code=count_var,
                )
            )

    async def reconcile_invitations(self, subject: str, profile: dict) -> None:
        """Provider membership plus a persisted local invite are both required."""
        from app.database import tenant_session

        email = verified_primary_email(profile)
        memberships = await self.provider.memberships_for_user(subject)
        for remote in memberships:
            org_id = remote.get("organization", {}).get("id")
            team = await self.db.scalar(
                select(Team).where(Team.clerk_org_id == org_id, Team.status == "active")
            )
            marker = remote.get("public_metadata", {}).get("firstout_invitation_id")
            if team is None or not marker:
                continue
            try:
                invitation_id = uuid.UUID(str(marker))
            except ValueError:
                continue
            async with tenant_session(team.id) as scoped:
                async with unit_of_work(scoped):
                    invite = await scoped.scalar(
                        select(TenantInvitation)
                        .where(
                            TenantInvitation.id == invitation_id,
                            TenantInvitation.team_id == team.id,
                        )
                        .with_for_update()
                    )
                    if (
                        invite is None
                        or invite.email != email
                        or invite.status not in {"pending", "accepted"}
                    ):
                        continue
                    user = await scoped.scalar(select(User).where(User.clerk_user_id == subject))
                    if user is None:
                        if await scoped.scalar(
                            select(User.id).where(func.lower(User.email) == email)
                        ):
                            continue  # Never link a legacy identity based only on matching email.
                        user = User(
                            team_id=team.id,
                            email=email,
                            clerk_user_id=subject,
                            password_hash="!clerk-only",
                            display_name=profile_name(profile),
                            role=invite.role,
                            is_disabled=False,
                        )
                        scoped.add(user)
                        await scoped.flush()
                    if user.is_disabled:
                        continue
                    existing = await scoped.scalar(
                        select(Membership).where(
                            Membership.user_id == user.id, Membership.team_id == team.id
                        )
                    )
                    if existing is None:
                        role = await scoped.scalar(
                            select(Role.id).where(Role.team_id == team.id, Role.slug == invite.role)
                        )
                        if role is None:
                            continue
                        scoped.add(
                            Membership(
                                team_id=team.id,
                                user_id=user.id,
                                role=invite.role,
                                permission_source="clerk",
                                is_disabled=False,
                                is_legacy_home=False,
                            )
                        )
                    invite.status = "accepted"


def profile_name(profile: dict) -> str:
    return (
        " ".join(str(profile.get(key) or "").strip() for key in ("first_name", "last_name")).strip()
        or profile.get("username")
        or ""
    )


class OrganisationService:
    def __init__(self, db: AsyncSession, provider: ClerkAPI) -> None:
        self.db = db
        self.provider = provider

    def _identity(self):
        identity = staff_identity_ctx.get()
        if identity is None:
            raise UnauthorizedError("Organisation membership is required")
        return identity

    async def current(self) -> dict:
        identity = self._identity()
        team = await self.db.get(Team, identity.team_id)
        count = await self.db.scalar(
            select(func.count())
            .select_from(Membership)
            .where(Membership.team_id == identity.team_id, Membership.is_disabled.is_(False))
        )
        return {
            **organisation_response(team, identity.role),
            "member_count": count,
            "max_members": await self._member_limit(team),
        }

    async def _member_limit(self, team: Team) -> int:
        if team.clerk_org_id and settings.clerk_secret_key:
            remote = await self.provider.organisation(team.clerk_org_id)
            limit = remote.get("max_allowed_memberships") if remote else None
            if isinstance(limit, int) and 0 < limit <= 20:
                return limit
            raise ValidationError("The organisation membership limit needs review")
        return MAX_MEMBERS

    async def invitations(self) -> list[dict]:
        identity = self._identity()
        await self._require_manage(identity.user_id)
        rows = await self.db.scalars(
            select(TenantInvitation)
            .where(TenantInvitation.team_id == identity.team_id)
            .order_by(TenantInvitation.created_at.desc())
        )
        return [invitation_response(row) for row in rows]

    async def invite(self, data: OrganisationInvitationCreate) -> dict:
        require_signup()
        identity = self._identity()
        await self._require_manage(identity.user_id)
        team = await self.db.get(Team, identity.team_id)
        user = await self.db.get(User, identity.user_id)
        if not team.clerk_org_id or not user.clerk_user_id:
            raise ValidationError(
                "Link this organisation and your account to Clerk before inviting staff"
            )
        email = str(data.email).lower()
        async with unit_of_work(self.db):
            await self.db.execute(select(Team.id).where(Team.id == team.id).with_for_update())
            role = await self.db.scalar(
                select(Role).where(Role.team_id == team.id, Role.slug == data.role)
            )
            if role is None:
                raise ValidationError("Select an existing Firstout role")
            if await self.db.scalar(
                select(User.id)
                .join(Membership, Membership.user_id == User.id)
                .where(Membership.team_id == team.id, func.lower(User.email) == email)
            ):
                raise ConflictError("This person already belongs to the organisation")
            invite = await self.db.scalar(
                select(TenantInvitation)
                .where(
                    TenantInvitation.team_id == team.id,
                    TenantInvitation.email == email,
                    TenantInvitation.status == "pending",
                )
                .with_for_update()
            )
            if invite is not None and invite.role != data.role:
                raise ConflictError("An invitation for this email already has a different role")
            if invite is None:
                active = await self.db.scalar(
                    select(func.count())
                    .select_from(Membership)
                    .where(Membership.team_id == team.id, Membership.is_disabled.is_(False))
                )
                pending = await self.db.scalar(
                    select(func.count())
                    .select_from(TenantInvitation)
                    .where(
                        TenantInvitation.team_id == team.id, TenantInvitation.status == "pending"
                    )
                )
                provider_members = await self.provider.members(team.clerk_org_id)
                limit = await self._member_limit(team)
                if max(active, len(provider_members)) + pending >= limit:
                    raise ValidationError(
                        f"This organisation supports {limit} staff, including its owner"
                    )
                invite = TenantInvitation(
                    team_id=team.id,
                    email=email,
                    role=data.role,
                    status="pending",
                    invited_by_user_id=user.id,
                )
                self.db.add(invite)
                await self.db.flush()
        # The local approval survives an upstream success followed by a lost response.
        async with unit_of_work(self.db):
            invite = await self.db.scalar(
                select(TenantInvitation).where(TenantInvitation.id == invite.id).with_for_update()
            )
            if not invite.clerk_invitation_id:
                remote = await self.provider.invite(
                    team.clerk_org_id,
                    email=email,
                    inviter=user.clerk_user_id,
                    invitation_id=str(invite.id),
                )
                invite.clerk_invitation_id = remote["id"]
        return invitation_response(invite)

    async def _require_manage(self, user_id: uuid.UUID) -> None:
        from app.services.permissions import PermissionService

        if "users.manage" not in await PermissionService(self.db).keys_for_user(user_id):
            raise UnauthorizedError("Staff management permission is required")

    async def revoke(self, invitation_id: uuid.UUID) -> None:
        identity = self._identity()
        await self._require_manage(identity.user_id)
        async with unit_of_work(self.db):
            invite = await self.db.scalar(
                select(TenantInvitation)
                .where(
                    TenantInvitation.id == invitation_id,
                    TenantInvitation.team_id == identity.team_id,
                )
                .with_for_update()
            )
            if invite is None:
                raise NotFoundError("Invitation not found")
            if invite.status == "accepted":
                raise ConflictError("This invitation has already been accepted")
            if invite.status == "revoked":
                return
            team = await self.db.get(Team, identity.team_id)
            user = await self.db.get(User, identity.user_id)
            if invite.clerk_invitation_id:
                await self.provider.revoke_invitation(
                    team.clerk_org_id, invite.clerk_invitation_id, user.clerk_user_id
                )
            else:
                # A lost create response may still have created the external invite.
                for remote in await self.provider.invitations(team.clerk_org_id):
                    if remote.get("public_metadata", {}).get("firstout_invitation_id") == str(
                        invite.id
                    ):
                        await self.provider.revoke_invitation(
                            team.clerk_org_id, remote["id"], user.clerk_user_id
                        )
            invite.status = "revoked"


def invitation_response(invite: TenantInvitation) -> dict:
    return {"id": invite.id, "email": invite.email, "role": invite.role, "status": invite.status}
