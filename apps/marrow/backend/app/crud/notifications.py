from __future__ import annotations

import datetime
import uuid
from typing import Optional

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import BaseCRUD
from app.models.notification import Notification
from f0rge_db.tenant import owned_by_user


class NotificationCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def list_for_user(self, limit: int) -> list[Notification]:
        stmt = (
            select(Notification)
            .where(owned_by_user(Notification.user_id))
            .order_by(Notification.created_at.desc())
            .limit(limit)
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def count_unread(self) -> int:
        stmt = (
            select(func.count())
            .select_from(Notification)
            .where(owned_by_user(Notification.user_id))
            .where(Notification.read_at.is_(None))
        )
        return int((await self.db.execute(stmt)).scalar_one())

    async def mark_read(self, ids: list[uuid.UUID], mark_all: bool) -> None:
        now = datetime.datetime.utcnow()
        stmt = (
            update(Notification)
            .where(owned_by_user(Notification.user_id))
            .where(Notification.read_at.is_(None))
        )
        if not mark_all:
            if not ids:
                return
            stmt = stmt.where(Notification.id.in_(ids))
        await self.db.execute(stmt.values(read_at=now))

    async def get_by_id(self, notification_id: uuid.UUID) -> Optional[Notification]:
        stmt = select(Notification).where(
            Notification.id == notification_id,
            owned_by_user(Notification.user_id),
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()
