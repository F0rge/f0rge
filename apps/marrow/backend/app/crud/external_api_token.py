from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import BaseCRUD
from app.models.external_api_token import ExternalApiToken
from f0rge_db.tenant import owned_by_user


class ExternalApiTokenCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def list_for_current_user(self) -> list[ExternalApiToken]:
        stmt = (
            select(ExternalApiToken)
            .where(owned_by_user(ExternalApiToken.user_id))
            .order_by(
                ExternalApiToken.created_at.asc().nulls_first(),
                ExternalApiToken.id.asc(),
            )
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def get_for_current_user(self, token_id: uuid.UUID) -> Optional[ExternalApiToken]:
        stmt = select(ExternalApiToken).where(
            ExternalApiToken.id == token_id,
            owned_by_user(ExternalApiToken.user_id),
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def any_for_current_user(self) -> bool:
        stmt = select(ExternalApiToken.id).where(owned_by_user(ExternalApiToken.user_id)).limit(1)
        return (await self.db.execute(stmt)).scalar_one_or_none() is not None
