"""Read-only Clerk-only cutover gate. Prints counts only, never credentials/PII."""

from __future__ import annotations

import asyncio
import json

import httpx
from sqlalchemy import select

from app.config import settings
from app.database import tenant_session
from app.models.customer_portal_user import CustomerPortalUser
from app.models.membership import Membership
from app.models.portal_identity import PortalAccess
from app.models.team import Team
from app.models.user import User
from app.services.clerk_api import ClerkAPI, verified_primary_email
from app.runtime_database import verify_portal_directory_grants


async def check_readiness(provider: ClerkAPI) -> dict:
    counts = {
        "active_staff": 0,
        "verified_staff": 0,
        "unready_staff": 0,
        "enabled_portal_accounts": 0,
        "unbound_portal_accounts": 0,
    }
    async with tenant_session() as db:
        await verify_portal_directory_grants(db)
        teams = list(await db.scalars(select(Team)))
        team_ids = [team.id for team in teams]
        team_by_id = {team.id: team for team in teams}
        staff = list(
            await db.scalars(select(User).where(User.is_disabled.is_(False), User.role != "system"))
        )
        for user in staff:
            memberships = list(
                await db.scalars(select(Membership).where(Membership.user_id == user.id))
            )
            enabled = [
                member
                for member in memberships
                if not member.is_disabled
                and member.team_id in team_by_id
                and team_by_id[member.team_id].status == "active"
            ]
            if memberships and not enabled:
                continue
            counts["active_staff"] += 1
            try:
                if not user.clerk_user_id or not enabled:
                    raise ValueError("Unlinked identity")
                remote = await provider.user(user.clerk_user_id)
                verified_primary_email(remote)
                if any(member.is_legacy_home for member in memberships) and (
                    remote.get("external_id") != str(user.id) or not remote.get("password_enabled")
                ):
                    raise ValueError("Imported identity mismatch")
                for member in enabled:
                    team = team_by_id[member.team_id]
                    if not team.clerk_org_id or not await provider.membership(
                        team.clerk_org_id, user.clerk_user_id
                    ):
                        raise ValueError("Missing canonical membership")
            except Exception:
                counts["unready_staff"] += 1
            else:
                counts["verified_staff"] += 1
    # FORCE RLS is respected: inspect each organisation using a fresh scoped
    # session. A no-context zero-row read must never be mistaken for readiness.
    for team_id in team_ids:
        async with tenant_session(team_id) as db:
            rows = list(
                await db.scalars(
                    select(CustomerPortalUser).where(
                        CustomerPortalUser.team_id == team_id,
                        CustomerPortalUser.is_disabled.is_(False),
                    )
                )
            )
            for portal in rows:
                counts["enabled_portal_accounts"] += 1
                binding = await db.scalar(
                    select(PortalAccess.id).where(
                        PortalAccess.organisation_id == team_id,
                        PortalAccess.portal_user_id == portal.id,
                        PortalAccess.customer_id == portal.customer_id,
                        PortalAccess.revoked_at.is_(None),
                    )
                )
                if binding is None:
                    counts["unbound_portal_accounts"] += 1
    return {
        "ready": bool(counts["active_staff"])
        and not (counts["unready_staff"] or counts["unbound_portal_accounts"]),
        **counts,
    }


async def run() -> dict:
    async with httpx.AsyncClient() as client:
        return await check_readiness(ClerkAPI(client, settings.clerk_secret_key))


if __name__ == "__main__":
    try:
        result = asyncio.run(run())
    except Exception:
        result = {"ready": False, "error": "Read-only preflight unavailable; cutover must stop"}
    print(json.dumps(result, sort_keys=True))
    raise SystemExit(0 if result["ready"] else 2)
