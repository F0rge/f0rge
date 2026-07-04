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
from app.services.obsidian_prefetch import render_and_write_daily_file
from app.services.photo_storage import delete_photo, resize_image, save_photo


async def next_photo_filename(db: AsyncSession, entry: Entry, ext: str = ".jpg") -> str:
    """Pick the next collision-free ``{date}_photo-N{ext}`` filename for ``entry``.

    Uses max(existing)+1, not count()+1, so a deleted photo never causes a
    number to be reused. Unions three sources of "used" numbers — DB rows,
    the local photo dir, and the vault attachments dir — so an orphan file
    (written to disk but never committed, or committed but not yet cleaned
    up from one of these locations) never collides with the next pick.
    """
    prefix = f"{entry.date.isoformat()}_photo-"
    suffix = ext
    used_numbers: set[int] = set()

    # Source 1: DB rows for this entry.
    rows = (await db.execute(select(Photo.filename).where(Photo.entry_id == entry.id))).all()
    for (existing_filename,) in rows:
        if existing_filename.startswith(prefix) and existing_filename.endswith(suffix):
            try:
                used_numbers.add(int(existing_filename[len(prefix) : -len(suffix)]))
            except ValueError:
                pass

    # Source 2: files in the local photos directory (catches orphans where
    # the file was written but the DB commit failed).
    photo_dir_abs = os.path.abspath(settings.photo_dir)
    if os.path.isdir(photo_dir_abs):
        for name in os.listdir(photo_dir_abs):
            if name.startswith(prefix) and name.endswith(suffix):
                try:
                    used_numbers.add(int(name[len(prefix) : -len(suffix)]))
                except ValueError:
                    pass

    # Source 3: vault attachments directory (catches vault-side orphans).
    vault_path = settings.vault_path
    if vault_path:
        vault_attachments = os.path.join(vault_path, "attachments")
        if os.path.isdir(vault_attachments):
            for name in os.listdir(vault_attachments):
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
            await self.db.execute(select(Photo).where(Photo.id == photo_id))
        ).scalar_one_or_none()
        if photo is None:
            raise NotFoundError(f"Photo {photo_id} not found")

        fields = data.model_fields_set
        label_changed = "label" in fields
        if label_changed:
            # ""/whitespace clears the label so the UI falls back to the AI dish_name.
            stripped = data.label.strip() if data.label is not None else None
            photo.label = stripped or None
        if "meal_time" in fields:
            photo.meal_time = data.meal_time

        await self.db.commit()
        await self.db.refresh(photo)

        # label appears in the vault daily file, meal_time doesn't — only
        # re-render when label actually changed (matches upload()/delete()).
        if label_changed:
            entry = (
                await self.db.execute(select(Entry).where(Entry.id == photo.entry_id))
            ).scalar_one()
            await self.db.refresh(entry)
            await render_and_write_daily_file(self.db, entry, entry.photos)

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
            await self.db.execute(select(Entry).where(Entry.date == entry_date))
        ).scalar_one_or_none()
        if entry is None:
            raise NotFoundError(f"No entry for {entry_date}")

        filename = await next_photo_filename(self.db, entry)
        vault_path = settings.vault_path

        raw_bytes = await file.read()
        processed_bytes = await asyncio.to_thread(resize_image, raw_bytes)
        await asyncio.to_thread(save_photo, processed_bytes, filename, vault_path)

        now = datetime.datetime.utcnow()

        # Strip timezone from meal_time before asyncpg binds to TIMESTAMP WITHOUT TIME ZONE.
        # Same fix as EntryCreate — convert tz-aware datetimes to UTC and drop tzinfo.
        normalized_meal_time = meal_time
        if normalized_meal_time is not None and normalized_meal_time.tzinfo is not None:
            utc_offset = normalized_meal_time.utcoffset()
            normalized_meal_time = (normalized_meal_time - utc_offset).replace(tzinfo=None)

        photo = Photo(
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
            await asyncio.to_thread(delete_photo, filename, vault_path)
            raise
        await self.db.refresh(photo)

        # Re-render vault to include the new photo embed.
        await self.db.refresh(entry)
        await render_and_write_daily_file(self.db, entry, entry.photos)

        # Queue analysis only when both the flag and the key are present.
        if settings.food_analysis_enabled and settings.openrouter_api_key:
            background_tasks.add_task(trigger_analysis_background, photo.id)

        return photo

    async def get_file_path(self, photo_id: int) -> str:
        photo = (
            await self.db.execute(select(Photo).where(Photo.id == photo_id))
        ).scalar_one_or_none()
        if photo is None:
            raise NotFoundError("Photo not found")
        file_path = os.path.join(os.path.abspath(settings.photo_dir), photo.filename)
        if not os.path.exists(file_path):
            raise NotFoundError("Photo file not found")
        return file_path

    async def delete(self, photo_id: int) -> None:
        photo = (
            await self.db.execute(select(Photo).where(Photo.id == photo_id))
        ).scalar_one_or_none()
        if photo is None:
            raise NotFoundError("Photo not found")
        entry = photo.entry
        filename = photo.filename
        vault_path = settings.vault_path

        # Commit DB delete before touching the filesystem. If the commit fails,
        # no files are removed and the DB row remains — consistent state.
        await self.db.delete(photo)
        await self.db.commit()

        # File cleanup happens after the successful commit.
        await asyncio.to_thread(delete_photo, filename, vault_path)

        # Re-render vault without the deleted photo.
        await self.db.refresh(entry)
        await render_and_write_daily_file(self.db, entry, entry.photos)
