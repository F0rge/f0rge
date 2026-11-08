"""Retryable explicit human staff migration; no email-based identity linking."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.team import Team
from app.models.user import User
from app.services.clerk_api import ClerkAPI, MAX_MEMBERS
from app.services.clerk_import import import_staff_user
from f0rge_core.exceptions import ConflictError, ValidationError
from f0rge_db.crud import unit_of_work


class StaffImportService:
    def __init__(self, db: AsyncSession, provider: ClerkAPI) -> None:
        self.db = db
        self.provider = provider

    async def run(self, team_id: uuid.UUID, *, commit: bool = False) -> dict:
        team = await self.db.get(Team, team_id)
        if team is None or team.status != "active":
            raise ValidationError("Select an existing active home organisation")
        users = list(
            await self.db.scalars(select(User).where(User.team_id == team_id).order_by(User.id))
        )
        humans = [
            user
            for user in users
            if user.role != "system" and user.email != "storefront-integration@system.example.com"
        ]
        unsupported = sum(not user.password_hash.startswith(("$2a$", "$2b$")) for user in humans)
        report = {
            "dry_run": not commit,
            "staff_count": len(humans),
            "disabled_count": sum(user.is_disabled for user in humans),
            "already_linked_count": sum(bool(user.clerk_user_id) for user in humans),
            "unsupported_hash_count": unsupported,
            "excluded_system_count": len(users) - len(humans),
            "imported_count": 0,
        }
        if not commit:
            return report
        if not settings.clerk_import_enabled or settings.tenant_isolation_mode != "enforced":
            raise ValidationError(
                "Explicit staff import requires enforced tenancy and CLERK_IMPORT_ENABLED"
            )
        if unsupported:
            raise ValidationError(
                "Unsupported staff hashes; retain legacy login and review migration"
            )
        if len(humans) > 20:
            raise ValidationError(
                "Staff count exceeds the reviewed Clerk membership limit; no users were imported"
            )
        owner = next(
            (user for user in humans if user.role == "owner" and not user.is_disabled), None
        )
        if owner is None:
            raise ValidationError("An active home owner is required")
        owner_id = owner.clerk_user_id or await self.provider.create_user(
            {
                "external_id": str(owner.id),
                "email_address": [owner.email],
                "password_digest": owner.password_hash,
                "password_hasher": "bcrypt",
                "create_organization_enabled": False,
            }
        )
        owner_remote = await self.provider.user(owner_id)
        if owner_remote.get("external_id") != str(owner.id):
            raise ConflictError("Clerk owner external ID does not match the staff UUID")
        async with unit_of_work(self.db):
            team = await self.db.scalar(select(Team).where(Team.id == team_id).with_for_update())
            if not team.clerk_org_id:
                team.clerk_org_id = await self.provider.ensure_organisation(
                    name=team.name,
                    slug=team.slug,
                    created_by=owner_id,
                    operation_id=str(
                        uuid.uuid5(uuid.NAMESPACE_URL, "firstout-staff-team:" + str(team.id))
                    ),
                    max_members=max(MAX_MEMBERS, len(humans)),
                )
        for user in humans:
            # Commit each verified external link independently. Retries recover
            # provider users by immutable external_id, never by email address.
            async with unit_of_work(self.db):
                user = await self.db.scalar(
                    select(User)
                    .where(User.id == user.id, User.team_id == team_id)
                    .with_for_update()
                )
                if user.clerk_user_id:
                    remote = await self.provider.user(user.clerk_user_id)
                    if remote.get("external_id") != str(user.id):
                        raise ConflictError("Clerk external ID does not match the staff UUID")
                await import_staff_user(user, team.clerk_org_id, self.provider)
            report["imported_count"] += 1
        return report
