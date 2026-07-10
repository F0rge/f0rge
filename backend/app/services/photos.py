from __future__ import annotations

import asyncio
import datetime
import os
from typing import Optional

from fastapi import BackgroundTasks, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.exceptions import NotFoundError
from app.models.entry import Entry
from app.models.photo import Photo
from app.schemas.photo import PhotoUpdate
from app.services.food_analysis import trigger_analysis_background
from app.services.photo_storage import delete_photo, resize_image, save_photo
from app.services import object_storage
from app.tenant import current_user_id, owned_by_user


async def next_photo_filename(db: AsyncSession, entry: Entry, ext: str = ".jpg") -> str:
    """Pick the next collision-free ``{date}_photo-N{ext}`` filename for ``entry``.

    Uses max(existing)+1, not count()+1, so a deleted photo never causes a
    number to be reused. Unions DB rows and the local photo dir so an orphan
    file (written to disk but never committed) never collides with the next pick.
    """
    prefix = f"{entry.date.isoformat()}_photo-"
    suffix = ext
    used_numbers: set[int] = set()

    # Source 1: DB rows for this entry.
    rows = (
        await db.execute(
            select(Photo.filename).where(owned_by_user(Photo.user_id), Photo.entry_id == entry.id)
        )
    ).all()
    for (existing_filename,) in rows:
        if existing_filename.startswith(prefix) and existing_filename.endswith(suffix):
            try:
                used_numbers.add(int(existing_filename[len(prefix) : -len(suffix)]))
            except ValueError:
                pass

    # Source 2: files on disk or in object storage (catches orphans).
    for name in object_storage.list_photo_filenames(prefix, user_id=str(entry.user_id)):
        if name.startswith(prefix) and name.endswith(suffix):
            try:
                used_numbers.add(int(name[len(prefix) : -len(suffix)]))
            except ValueError:
                pass

    photo_number = max(used_numbers, default=0) + 1
    return f"{prefix}{photo_number}{suffix}"


class PhotoService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def update_photo(self, photo_id: int, data: PhotoUpdate) -> Photo:
        photo = (
            await self.db.execute(
                select(Photo).where(owned_by_user(Photo.user_id), Photo.id == photo_id)
            )
        ).scalar_one_or_none()
        if photo is None:
            raise NotFoundError(f"Photo {photo_id} not found")

        fields = data.model_fields_set
        if "label" in fields:
            # ""/whitespace clears the label so the UI falls back to the AI dish_name.
            stripped = data.label.strip() if data.label is not None else None
            photo.label = stripped or None
        if "meal_time" in fields:
            photo.meal_time = data.meal_time

        await self.db.commit()
        await self.db.refresh(photo)
        return photo

    async def upload(
        self,
        entry_date: datetime.date,
        file: UploadFile,
        label: Optional[str],
        meal_time: Optional[datetime.datetime],
        background_tasks: BackgroundTasks,
    ) -> Photo:
        entry = (
            await self.db.execute(
                select(Entry).where(owned_by_user(Entry.user_id), Entry.date == entry_date)
            )
        ).scalar_one_or_none()
        if entry is None:
            raise NotFoundError(f"No entry for {entry_date}")

        filename = await next_photo_filename(self.db, entry)

        raw_bytes = await file.read()
        processed_bytes = await asyncio.to_thread(resize_image, raw_bytes)
        await asyncio.to_thread(
            save_photo, processed_bytes, filename, user_id=str(current_user_id())
        )

        now = datetime.datetime.utcnow()

        # Strip timezone from meal_time before asyncpg binds to TIMESTAMP WITHOUT TIME ZONE.
        # Same fix as EntryCreate — convert tz-aware datetimes to UTC and drop tzinfo.
        normalized_meal_time = meal_time
        if normalized_meal_time is not None and normalized_meal_time.tzinfo is not None:
            utc_offset = normalized_meal_time.utcoffset()
            normalized_meal_time = (normalized_meal_time - utc_offset).replace(tzinfo=None)

        photo = Photo(
            user_id=current_user_id(),
            entry_id=entry.id,
            filename=filename,
            label=label,
            original_filename=file.filename,
            meal_time=normalized_meal_time if normalized_meal_time is not None else now,
            created_at=now,
        )
        # Invariant: a file on disk implies a DB row exists.
        # If the commit fails we clean up the file so the next upload
        # doesn't collide with a phantom on disk.
        self.db.add(photo)
        try:
            await self.db.commit()
        except Exception:
            await asyncio.to_thread(delete_photo, filename, user_id=str(current_user_id()))
            raise
        await self.db.refresh(photo)

        # Queue analysis when enabled and credentials resolve (env or BYOK).
        # Credential resolution must not fail the upload — the photo is already persisted.
        if settings.food_analysis_enabled:
            from app.services.llm.factory import resolve_llm_credentials

            try:
                api_key, _ = await resolve_llm_credentials(self.db)
            except Exception:
                api_key = None
            if api_key:
                background_tasks.add_task(trigger_analysis_background, photo.id, photo.user_id)

        return photo

    async def get_file_path(self, photo_id: int) -> str:
        photo = (
            await self.db.execute(
                select(Photo).where(owned_by_user(Photo.user_id), Photo.id == photo_id)
            )
        ).scalar_one_or_none()
        if photo is None:
            raise NotFoundError("Photo not found")
        if not object_storage.exists_relative(photo.filename, user_id=str(photo.user_id)):
            raise NotFoundError("Photo file not found")
        presigned = object_storage.presigned_url_for_relative(
            photo.filename, user_id=str(photo.user_id)
        )
        if presigned:
            return presigned
        return os.path.join(os.path.abspath(settings.photo_dir), photo.filename)

    async def delete(self, photo_id: int) -> None:
        photo = (
            await self.db.execute(
                select(Photo).where(owned_by_user(Photo.user_id), Photo.id == photo_id)
            )
        ).scalar_one_or_none()
        if photo is None:
            raise NotFoundError("Photo not found")
        filename = photo.filename

        # Commit DB delete before touching the filesystem. If the commit fails,
        # no files are removed and the DB row remains — consistent state.
        await self.db.delete(photo)
        await self.db.commit()

        # File cleanup happens after the successful commit.
        await asyncio.to_thread(delete_photo, filename, user_id=str(photo.user_id))
