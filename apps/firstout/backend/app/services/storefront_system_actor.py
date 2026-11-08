from __future__ import annotations

import secrets
import uuid

from sqlalchemy import select
from sqlalchemy.orm import defer
from typing import Optional
from app.crud.user import require_directory_tenant
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.team import Team
from app.models.membership import Membership
from app.models.user import User
from app.services.auth import hash_password
from f0rge_core.exceptions import ValidationError
from f0rge_db.crud import unit_of_work

STOREFRONT_ACTOR_EMAIL = "storefront-integration@system.example.com"


class StorefrontSystemActorService:
    """Own the disabled per-instance user used to attribute automated stock movements."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def ensure(self, company_id: Optional[uuid.UUID] = None) -> User:
        tenant_id = require_directory_tenant()
        if company_id is not None and company_id != tenant_id:
            raise ValidationError("Storefront company does not match tenant context")
        team = await self.db.get(Team, tenant_id)
        if team is None:
            raise ValidationError("Storefront operational company is unavailable")
        actor_email = (
            STOREFRONT_ACTOR_EMAIL
            if team.slug == "firstout"
            else f"storefront-{team.id}@system.example.com"
        )
        actor = await self.db.scalar(
            select(User)
            .options(defer(User.password_hash, raiseload=True))
            .where(User.email == actor_email)
        )
        if actor is not None:
            if actor.team_id != team.id or actor.role != "system" or not actor.is_disabled:
                raise ValidationError("Storefront system actor is not safely configured")
            return actor

        actor = User(
            team_id=team.id,
            email=actor_email,
            password_hash=hash_password(secrets.token_urlsafe(48)),
            display_name="Storefront integration (system)",
            role="system",
            is_disabled=True,
        )
        async with unit_of_work(self.db):
            self.db.add(actor)
            await self.db.flush()
            self.db.add(
                Membership(
                    user_id=actor.id,
                    team_id=team.id,
                    role="system",
                    permission_source="legacy",
                    is_disabled=True,
                    is_legacy_home=True,
                )
            )
        return actor
