from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.nia import NiaUsageEventCRUD
from app.models.nia import NiaUsageEvent
from f0rge_db.crud import unit_of_work


class NiaUsageService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = NiaUsageEventCRUD(db)

    async def record_usage(
        self,
        *,
        user_id: uuid.UUID,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: Optional[int] = None,
        thread_id: Optional[uuid.UUID] = None,
        openrouter_generation_id: Optional[str] = None,
    ) -> NiaUsageEvent:
        resolved_total = (
            total_tokens if total_tokens is not None else prompt_tokens + completion_tokens
        )
        event = NiaUsageEvent(
            user_id=user_id,
            thread_id=thread_id,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=resolved_total,
            openrouter_generation_id=openrouter_generation_id,
        )
        async with unit_of_work(self.db):
            await self.crud.add_and_flush(event)
        return event

    async def sum_total_tokens_for_user(self, user_id: uuid.UUID) -> int:
        return await self.crud.sum_total_tokens_for_user(user_id)
