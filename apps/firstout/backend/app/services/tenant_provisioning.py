"""Explicit, default-off test provisioning; never run by webhook or startup.

Providers are injected (test fakes in this PR). No live billing transport exists.
The caller owns commit and retry/compensation for the external organisation.
"""

from __future__ import annotations

from typing import Optional

from typing import Protocol
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.models.membership import Membership
from app.models.role import Role, RolePermission
from app.models.team import Team
from app.models.user import User
from app.permissions import ROLE_PRESETS, ROLE_PRESET_NAMES
from app.services.tenant_host import validate_slug
from f0rge_db.organisation import apply_tenant_context, tenant_id_ctx

CLERK_ROLE_PRESETS = {
    "org:admin": "owner",
    "org:owner": "owner",
    "org:buyer": "buyer",
    "org:warehouse": "warehouse",
    "org:till": "till",
    "org:books": "books",
}


class OrganisationProvider(Protocol):
    async def create_organisation(self, *, name: str, slug: str, created_by: str) -> str: ...


def require_test_provisioning() -> None:
    if not settings.tenant_signup_enabled:
        raise ValueError("Tenant provisioning is disabled")
    if not settings.billing_disabled or not settings.billing_test_mode:
        raise ValueError("Only billing-disabled test provisioning is implemented")


async def provision_tenant(
    db: AsyncSession, *, owner: User, name: str, slug: str, provider: OrganisationProvider
) -> Team:
    require_test_provisioning()
    validate_slug(slug)
    if not owner.clerk_user_id or owner.is_disabled:
        raise ValueError("An active explicitly-linked Clerk owner is required")
    if tenant_id_ctx.get() is not None:
        raise ValueError("Provision using a fresh identity-directory session")
    if await db.scalar(select(Team.id).where(Team.slug == slug)):
        raise ValueError("Tenant slug is already in use")
    org_id = await provider.create_organisation(
        name=name, slug=slug, created_by=owner.clerk_user_id
    )
    team = Team(name=name, slug=slug, status="active", clerk_org_id=org_id)
    db.add(team)
    await db.flush()
    await apply_tenant_context(db, team.id)
    token = tenant_id_ctx.set(team.id)
    try:
        for role_slug, keys in ROLE_PRESETS.items():
            db.add(
                Role(
                    team_id=team.id,
                    slug=role_slug,
                    name=ROLE_PRESET_NAMES[role_slug],
                    is_system=True,
                    is_owner_preset=role_slug == "owner",
                    permissions=[RolePermission(team_id=team.id, key=key) for key in sorted(keys)],
                )
            )
        db.add(
            Membership(
                user_id=owner.id,
                team_id=team.id,
                role="owner",
                permission_source="clerk",
                is_legacy_home=False,
                is_disabled=False,
            )
        )
        await db.flush()
    finally:
        tenant_id_ctx.reset(token)
    # No bootstrap locations are copied. Billing does not participate in access.
    return team


async def provision_invited_membership(
    db: AsyncSession, *, user: User, team: Team, clerk_role: str, local_role: Optional[str] = None
) -> Membership:
    """Call only after explicit invite approval and provider membership verification.

    Clerk org:member has no implicit shop grants: a local role must be selected.
    Existing memberships are returned untouched, preserving richer grants.
    """
    require_test_provisioning()
    if not user.clerk_user_id or user.is_disabled or not team.clerk_org_id:
        raise ValueError("Explicit linked active identities are required")
    existing = await db.scalar(
        select(Membership).where(Membership.user_id == user.id, Membership.team_id == team.id)
    )
    if existing is not None:
        return existing
    slug = local_role or CLERK_ROLE_PRESETS.get(clerk_role)
    if not slug:
        raise ValueError("Select an explicit Firstout role for org:member")
    await apply_tenant_context(db, team.id)
    role = await db.scalar(select(Role).where(Role.team_id == team.id, Role.slug == slug))
    if role is None:
        raise ValueError("Unknown Firstout role")
    member = Membership(
        user_id=user.id,
        team_id=team.id,
        role=slug,
        permission_source="clerk",
        is_legacy_home=False,
        is_disabled=False,
    )
    db.add(member)
    await db.flush()
    return member
