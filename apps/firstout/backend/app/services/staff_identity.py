from __future__ import annotations

from typing import Optional

import uuid
from dataclasses import dataclass
from contextvars import ContextVar
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.models.membership import Membership
from app.models.team import Team
from app.models.user import User


@dataclass(frozen=True)
class StaffIdentity:
    user_id: uuid.UUID
    team_id: uuid.UUID
    team_name: str
    team_slug: str
    role: str
    default_location_id: Optional[uuid.UUID]
    clerk: bool = False


staff_identity_ctx: ContextVar[Optional[StaffIdentity]] = ContextVar(
    "firstout_staff_identity", default=None
)


async def resolve_membership(
    db: AsyncSession, user: User, *, clerk_org_id: Optional[str] = None
) -> StaffIdentity:
    query = (
        select(Membership, Team)
        .join(Team, Team.id == Membership.team_id)
        .where(Membership.user_id == user.id)
    )
    if clerk_org_id:
        query = query.where(Team.clerk_org_id == clerk_org_id)
    else:
        query = query.where(Membership.is_legacy_home.is_(True), Membership.team_id == user.team_id)
    row = (await db.execute(query)).one_or_none()
    if row is None or user.is_disabled:
        raise HTTPException(401, "Invalid membership")
    membership, team = row
    if settings.tenant_isolation_mode == "single_home" and (
        team.slug != "firstout" or clerk_org_id is not None
    ):
        raise HTTPException(403, "Tenant cutover is not active")
    if membership.is_disabled:
        raise HTTPException(401, "Invalid membership")
    if team.status != "active":
        raise HTTPException(403, "Membership unavailable")
    # Original home grants remain authoritative after the authentication cutover;
    # Clerk's coarse roles never rewrite legitimate staff administration.
    role = user.role if membership.is_legacy_home else membership.role
    location = (
        user.default_location_id if membership.is_legacy_home else membership.default_location_id
    )
    return StaffIdentity(user.id, team.id, team.name, team.slug, role, location, bool(clerk_org_id))
