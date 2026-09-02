from __future__ import annotations

import datetime
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.nia import NiaThreadCRUD
from app.crud.user import UserCRUD
from app.models.nia import NiaMessage, NiaThread
from app.schemas.nia import (
    NiaMessageResponse,
    NiaThreadCreate,
    NiaThreadResponse,
    NiaThreadSummaryResponse,
)
from f0rge_core.exceptions import NotFoundError
from f0rge_db.crud import unit_of_work

DEFAULT_THREAD_TITLE = "New thread"


class NiaThreadsService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = NiaThreadCRUD(db)
        self.user_crud = UserCRUD(db)

    async def list_threads(self, user_id: uuid.UUID) -> list[NiaThreadSummaryResponse]:
        rows = await self.crud.list_active_for_user(user_id)
        return [self._to_summary(row) for row in rows]

    async def create_thread(
        self,
        user_id: uuid.UUID,
        data: NiaThreadCreate,
    ) -> NiaThreadResponse:
        user = await self.user_crud.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found")
        title = data.title.strip() if data.title and data.title.strip() else DEFAULT_THREAD_TITLE
        thread = NiaThread(
            user_id=user_id,
            team_id=user.team_id,
            title=title,
        )
        async with unit_of_work(self.db):
            await self.crud.add_and_flush(thread)
        return self._to_response(await self._get_owned_or_404(thread.id, user_id))

    async def get_thread(
        self,
        user_id: uuid.UUID,
        thread_id: uuid.UUID,
    ) -> NiaThreadResponse:
        return self._to_response(await self._get_owned_or_404(thread_id, user_id))

    async def append_message(
        self,
        user_id: uuid.UUID,
        thread_id: uuid.UUID,
        role: str,
        content: str,
    ) -> None:
        thread = await self._get_owned_or_404(thread_id, user_id)
        message = NiaMessage(
            thread_id=thread.id,
            role=role,
            content=content,
        )
        async with unit_of_work(self.db):
            await self.crud.add_and_flush(message)
            thread.updated_at = datetime.datetime.utcnow()

    async def archive_thread(
        self,
        user_id: uuid.UUID,
        thread_id: uuid.UUID,
    ) -> NiaThreadSummaryResponse:
        thread = await self._get_owned_or_404(thread_id, user_id)
        if thread.archived_at is None:
            async with unit_of_work(self.db):
                thread.archived_at = datetime.datetime.utcnow()
        return self._to_summary(thread)

    async def _get_owned_or_404(
        self,
        thread_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> NiaThread:
        thread = await self.crud.get_owned(thread_id, user_id)
        if thread is None:
            raise NotFoundError("Thread not found")
        return thread

    def _to_summary(self, thread: NiaThread) -> NiaThreadSummaryResponse:
        return NiaThreadSummaryResponse.model_validate(thread)

    def _to_response(self, thread: NiaThread) -> NiaThreadResponse:
        return NiaThreadResponse(
            id=thread.id,
            title=thread.title,
            created_at=thread.created_at,
            updated_at=thread.updated_at,
            archived_at=thread.archived_at,
            messages=[NiaMessageResponse.model_validate(msg) for msg in thread.messages],
        )
