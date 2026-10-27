from __future__ import annotations

import datetime
import uuid
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.password_reset_token import PasswordResetToken
from f0rge_db.crud import BaseCRUD


class PasswordResetTokenCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_hash_for_update(self, token_hash: str) -> Optional[PasswordResetToken]:
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
            )
            .values(used_at=now)
        )
