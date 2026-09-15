from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.customer_portal_user import CustomerPortalUser
from f0rge_db.crud import BaseCRUD


class CustomerPortalUserCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_id(self, portal_user_id: uuid.UUID) -> Optional[CustomerPortalUser]:
        return (
            await self.db.execute(
                select(CustomerPortalUser)
                .options(selectinload(CustomerPortalUser.customer))
                .where(CustomerPortalUser.id == portal_user_id)
            )
        ).scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[CustomerPortalUser]:
        return (
            await self.db.execute(
                select(CustomerPortalUser)
                .options(selectinload(CustomerPortalUser.customer))
                .where(CustomerPortalUser.email == email.strip().lower())
            )
        ).scalar_one_or_none()
