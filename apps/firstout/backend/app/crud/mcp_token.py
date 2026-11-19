from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mcp_token import McpToken, McpTokenActivity
from app.models.membership import Membership
from app.models.team import Team
from app.models.user import User
from f0rge_db.crud import BaseCRUD


class McpTokenCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession, team_id: uuid.UUID) -> None:
        super().__init__(db)
        self.team_id = team_id

    def _tokens(self):
        return select(McpToken).where(McpToken.team_id == self.team_id)

    async def tokens(self, user_id: uuid.UUID) -> list[McpToken]:
        return list(
            await self.db.scalars(
                self._tokens()
                .where(McpToken.user_id == user_id)
                .order_by(McpToken.created_at.desc(), McpToken.id.desc())
            )
        )

    async def recent_activity(self, user_id: uuid.UUID, limit: int) -> list[McpTokenActivity]:
        return list(
            await self.db.scalars(
                select(McpTokenActivity)
                .where(
                    McpTokenActivity.team_id == self.team_id, McpTokenActivity.user_id == user_id
                )
                .order_by(McpTokenActivity.occurred_at.desc(), McpTokenActivity.id.desc())
                .limit(limit)
            )
        )

    async def lock_owned(self, user_id: uuid.UUID, token_id: uuid.UUID) -> Optional[McpToken]:
        return await self.db.scalar(
            self._tokens()
            .where(McpToken.user_id == user_id, McpToken.id == token_id)
            .with_for_update()
        )

    async def find_for_authentication(
        self, digest: str, *, for_update: bool = False
    ) -> Optional[McpToken]:
        query = self._tokens().where(McpToken.digest == digest)
        if for_update:
            query = query.with_for_update()
        return await self.db.scalar(query)

    async def active_clerk_identity(
        self, user_id: uuid.UUID, *, for_update: bool = False
    ) -> Optional[tuple[str, str]]:
        query = (
            select(User.clerk_user_id, Team.clerk_org_id)
            .select_from(Membership)
            .join(User, User.id == Membership.user_id)
            .join(Team, Team.id == Membership.team_id)
            .where(
                Membership.team_id == self.team_id,
                Membership.user_id == user_id,
                Membership.is_disabled.is_(False),
                User.is_disabled.is_(False),
                User.role != "system",
                User.clerk_user_id.is_not(None),
                Team.status == "active",
                Team.clerk_org_id.is_not(None),
            )
        )
        if for_update:
            query = query.with_for_update(of=Membership)
        row = (await self.db.execute(query)).one_or_none()
        if row is None:
            return None
        subject, organisation = row
        return (subject, organisation) if subject and organisation else None

    async def active_name_exists(self, user_id: uuid.UUID, name: str, now: datetime) -> bool:
        return (
            await self.db.scalar(
                select(McpToken.id).where(
                    McpToken.team_id == self.team_id,
                    McpToken.user_id == user_id,
                    func.lower(McpToken.name) == func.lower(name),
                    McpToken.expires_at > now,
                    McpToken.revoked_at.is_(None),
                )
            )
            is not None
        )
