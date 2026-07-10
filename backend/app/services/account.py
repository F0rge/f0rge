from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Callable
from functools import partial

from fastapi import Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.crud.auth import UserCRUD
from app.crud.labs import LabCRUD
from app.crud.photos import PhotoCRUD
from app.exceptions import NotFoundError, UnauthorizedError, ValidationError
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
from app.services.avatar_storage import (
    avatar_exists,
    delete_avatar,
    resize_avatar,
    save_avatar,
)
from app.services.photo_storage import delete_photo
from app.tenant import current_user_id

logger = logging.getLogger(__name__)

ALLOWED_AVATAR_CONTENT_TYPES = frozenset(
    {
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/heic",
        "image/heif",
    }
)
MAX_AVATAR_BYTES = 5 * 1024 * 1024


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
            avatar_default_index=user.avatar_default_index,
            has_custom_avatar=user.avatar_custom_filename is not None,
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

    async def upload_avatar(self, file: UploadFile) -> AccountResponse:
        user = await self._get_current_user()
        content_type = file.content_type or ""
        if content_type not in ALLOWED_AVATAR_CONTENT_TYPES:
            raise ValidationError("Avatar must be a JPEG, PNG, WebP, or HEIC image")

        raw_bytes = await file.read()
        if not raw_bytes:
            raise ValidationError("Avatar file is empty")
        if len(raw_bytes) > MAX_AVATAR_BYTES:
            raise ValidationError("Avatar must be 5 MB or smaller")

        processed = await asyncio.to_thread(resize_avatar, raw_bytes)
        relative_path = await asyncio.to_thread(save_avatar, processed, user_id=str(user.id))
        user.avatar_custom_filename = relative_path
        user = await self.crud.commit_refresh(user)
        return self._to_response(user)

    async def delete_avatar(self) -> AccountResponse:
        user = await self._get_current_user()
        if user.avatar_custom_filename is None:
            return self._to_response(user)

        await asyncio.to_thread(delete_avatar, user_id=str(user.id))
        user.avatar_custom_filename = None
        user = await self.crud.commit_refresh(user)
        return self._to_response(user)

    async def get_avatar_file_target(self) -> str:
        user = await self._get_current_user()
        if user.avatar_custom_filename is None:
            raise NotFoundError("No custom avatar")
        if not avatar_exists(user_id=str(user.id)):
            raise NotFoundError("Avatar file not found")

        presigned = object_storage.presigned_url_for_relative(
            user.avatar_custom_filename,
            user_id=str(user.id),
        )
        if presigned:
            return presigned
        return os.path.join(
            os.path.abspath(settings.photo_dir),
            user.avatar_custom_filename,
        )

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
        had_custom_avatar = user.avatar_custom_filename is not None

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

        cleanup_tasks = [
            *(
                _delete_soft(partial(delete_photo, name, user_id=str(user_id)), name)
                for name in filenames
            ),
            *(_delete_soft(partial(object_storage.delete_object, ref), ref) for ref in lab_refs),
        ]
        if had_custom_avatar:
            cleanup_tasks.append(
                _delete_soft(partial(delete_avatar, user_id=str(user_id)), "avatar")
            )
        await asyncio.gather(*cleanup_tasks)
