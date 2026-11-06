from __future__ import annotations

import datetime
import uuid
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.user import ScopedDirectoryCRUD, require_directory_tenant
from app.models.membership import Membership
from app.models.password_reset_token import PasswordResetToken


class PasswordResetTokenCRUD(ScopedDirectoryCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_hash_for_update(self, token_hash: str) -> Optional[PasswordResetToken]:
        """Pre-auth capability lookup by high-entropy token hash, never enumeration."""
        result = await self.db.execute(
            select(PasswordResetToken)
            .where(PasswordResetToken.token_hash == token_hash)
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def invalidate_unused(self, user_id: uuid.UUID, now: datetime.datetime) -> None:
        await self.db.execute(
            update(PasswordResetToken)
            .where(
                PasswordResetToken.user_id == user_id,
                PasswordResetToken.used_at.is_(None),
                PasswordResetToken.user_id.in_(
                    select(Membership.user_id).where(
                        Membership.team_id == require_directory_tenant()
                    )
                ),
            )
            .values(used_at=now)
        )
