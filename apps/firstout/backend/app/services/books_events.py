from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.books_event import BooksEventCRUD
from app.crud.user import UserCRUD
from app.models.books_event import BooksDocumentType, BooksEvent, BooksEventAction
from app.schemas.books_event import BooksEventResponse


class BooksEventService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = BooksEventCRUD(db)
        self.users = UserCRUD(db)

    async def record(
        self,
        document_type: BooksDocumentType,
        document_id: uuid.UUID,
        action: BooksEventAction,
        actor_user_id: Optional[uuid.UUID] = None,
        note: Optional[str] = None,
    ) -> None:
        await self.crud.add_and_flush(
            BooksEvent(
                document_type=document_type,
                document_id=document_id,
                action=action,
                actor_user_id=actor_user_id,
                note=note,
            )
        )

    async def list(
        self,
        document_type: BooksDocumentType,
        document_id: uuid.UUID,
    ) -> list[BooksEventResponse]:
        events = await self.crud.list_for_document(document_type, document_id)
        emails: dict[uuid.UUID, Optional[str]] = {}
        for event in events:
            if event.actor_user_id is None or event.actor_user_id in emails:
                continue
            user = await self.users.get_by_id(event.actor_user_id)
            emails[event.actor_user_id] = user.email if user is not None else None
        return [
            BooksEventResponse(
                id=event.id,
                document_type=event.document_type,
                document_id=event.document_id,
                action=event.action,
                actor_user_id=event.actor_user_id,
                actor_email=emails.get(event.actor_user_id) if event.actor_user_id else None,
                note=event.note,
                created_at=event.created_at,
            )
            for event in events
        ]
