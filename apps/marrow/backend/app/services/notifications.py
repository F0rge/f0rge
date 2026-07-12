from __future__ import annotations

import json
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.notifications import NotificationCRUD

# Notification type strings used by social features:
# connection_request, connection_accepted, group_invite, group_invite_accepted,
# meal_tag_request, meal_tag_delivered


class NotificationService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = NotificationCRUD(db)

    async def list_notifications(self, limit: int) -> list:
        return await self.crud.list_for_user(limit)

    async def unread_count(self) -> int:
        return await self.crud.count_unread()

    async def mark_read(self, ids: list[uuid.UUID], mark_all: bool) -> None:
        await self.crud.mark_read(ids, mark_all)
        await self.crud.save()

    async def notify(self, recipient_id: uuid.UUID, type: str, payload: dict) -> None:
        """Insert a notification for ANY user via create_notification SECURITY DEFINER."""
        await self.db.execute(
            text("SELECT create_notification(:r, :t, cast(:p as jsonb))"),
            {"r": str(recipient_id), "t": type, "p": json.dumps(payload)},
        )
