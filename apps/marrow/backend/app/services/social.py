from __future__ import annotations

import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.social import SocialCRUD
from f0rge_core.exceptions import ConflictError, NotFoundError
from app.schemas.social import (
    PublicUserCard,
    validate_handle_format,
)


class SocialService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = SocialCRUD(db)

    @staticmethod
    def to_public_card(user) -> PublicUserCard:
        return PublicUserCard(
            handle=user.handle,
            display_name=user.display_name,
            avatar_default_index=user.avatar_default_index,
        )

    async def check_handle_available(self, handle: str) -> bool:
        try:
            normalized = validate_handle_format(handle)
        except Exception:
            return False
        return not await self.crud.is_handle_taken(normalized)

    async def lookup_by_handle(self, handle: str) -> PublicUserCard:
        user = await self.crud.get_by_handle(handle)
        if user is None or user.handle is None:
            raise NotFoundError("No user with that handle")
        return self.to_public_card(user)

    async def assert_handle_available(
        self, handle: str, exclude_user_id: uuid.UUID | None = None
    ) -> str:
        normalized = validate_handle_format(handle)
        existing = await self.crud.get_by_handle(normalized)
        if existing is not None and (exclude_user_id is None or existing.id != exclude_user_id):
            raise ConflictError("Handle already taken")
        return normalized

    async def set_user_handle(self, user, handle: str):
        normalized = await self.assert_handle_available(handle, exclude_user_id=user.id)
        user.handle = normalized
        try:
            return await self.crud.commit_refresh(user)
        except IntegrityError as exc:
            raise ConflictError("Handle already taken") from exc
