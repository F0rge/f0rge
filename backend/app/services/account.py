from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from functools import partial

from fastapi import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.crud.auth import UserCRUD
from app.crud.labs import LabCRUD
from app.crud.photos import PhotoCRUD
from app.exceptions import UnauthorizedError, ValidationError
from app.models.user import User
from app.schemas.account import (
    AccountDeleteRequest,
    AccountResponse,
    AccountUpdate,
    PasswordChangeRequest,
)
from app.services import object_storage
from app.services.auth import (
    clear_session_cookie,
    hash_password,
    validate_password,
    verify_password,
)
from app.services.photo_storage import delete_photo
from app.tenant import current_user_id

logger = logging.getLogger(__name__)


class AccountService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = UserCRUD(db)

    @staticmethod
    def _to_response(user: User) -> AccountResponse:
        return AccountResponse(
            user_id=str(user.id),
            email=user.email,
            display_name=user.display_name,
            created_at=user.created_at,
        )

    async def _get_current_user(self) -> User:
        user = await self.crud.get_by_id(current_user_id())
        if user is None:
            raise UnauthorizedError("Invalid session")
        return user

    async def get(self) -> AccountResponse:
        user = await self._get_current_user()
        return self._to_response(user)

    async def update(self, data: AccountUpdate) -> AccountResponse:
        user = await self._get_current_user()
        if "display_name" in data.model_fields_set:
            user.display_name = (data.display_name or "").strip() or None
            user = await self.crud.commit_refresh(user)
        return self._to_response(user)

    async def change_password(self, data: PasswordChangeRequest) -> None:
        user = await self._get_current_user()
        if not verify_password(data.current_password, user.password_hash):
            raise ValidationError("Current password is incorrect")
        validate_password(data.new_password)
        user.password_hash = hash_password(data.new_password)
        await self.crud.commit_refresh(user)

    async def delete(self, data: AccountDeleteRequest, response: Response) -> None:
        user = await self._get_current_user()
        if not verify_password(data.password, user.password_hash):
            raise ValidationError("Incorrect password")
        if str(user.id) == settings.default_storage_user_id:
            raise ValidationError("This account cannot be deleted")

        # Snapshot storage refs before the DB row (and its ON DELETE CASCADE
        # graph across all 23 user-owned tables) is gone. Lab attachments are
        # purged only from object storage (user-prefixed keys); local lab files
        # are content-addressed and shared across users, so they must survive.
        user_id = user.id
        filenames = await PhotoCRUD(self.db).list_filenames_for_user()
        lab_refs = {
            ref
            for ref in await LabCRUD(self.db).list_attachment_paths_for_user()
            if object_storage.is_remote_storage_ref(ref)
        }

        await self.crud.delete_and_commit(user)
        clear_session_cookie(response)

        # Storage cleanup happens after the successful commit, mirroring
        # PhotoService.delete's DB-first-then-filesystem ordering. Deletes run
        # concurrently and soft-fail per object so one bad delete doesn't
        # strand the rest — the DB rows are already gone either way.
        async def _delete_soft(thunk: Callable[[], None], ref: str) -> None:
            try:
                await asyncio.to_thread(thunk)
            except Exception:
                logger.warning(
                    "Failed to delete storage object %s for deleted user %s",
                    ref,
                    user_id,
                    exc_info=True,
                )

        await asyncio.gather(
            *(
                _delete_soft(partial(delete_photo, name, user_id=str(user_id)), name)
                for name in filenames
            ),
            *(_delete_soft(partial(object_storage.delete_object, ref), ref) for ref in lab_refs),
        )
