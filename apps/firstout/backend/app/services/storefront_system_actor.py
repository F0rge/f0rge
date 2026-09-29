from __future__ import annotations

import secrets
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.team import Team
from app.models.user import User
from app.services.auth import hash_password
from f0rge_core.exceptions import ValidationError
from f0rge_db.crud import unit_of_work

STOREFRONT_ACTOR_EMAIL = "storefront-integration@system.example.com"


class StorefrontSystemActorService:
    """Own the disabled per-instance user used to attribute automated stock movements."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def ensure(self, company_id: uuid.UUID | None = None) -> User:
        team = (
            await self.db.get(Team, company_id)
            if company_id
            else await self.db.scalar(select(Team))
        )
        if team is None:
            raise ValidationError("Storefront operational company is unavailable")
        actor = await self.db.scalar(select(User).where(User.email == STOREFRONT_ACTOR_EMAIL))
        if actor is not None:
            if actor.team_id != team.id or actor.role != "system" or not actor.is_disabled:
                raise ValidationError("Storefront system actor is not safely configured")
            return actor

        actor = User(
            team_id=team.id,
            email=STOREFRONT_ACTOR_EMAIL,
            password_hash=hash_password(secrets.token_urlsafe(48)),
            display_name="Storefront integration (system)",
            role="system",
            is_disabled=True,
        )
        async with unit_of_work(self.db):
            self.db.add(actor)
            await self.db.flush()
        return actor
