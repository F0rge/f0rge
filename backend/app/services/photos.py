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
from app.services.food_analysis import trigger_analysis_background
from app.services.obsidian_prefetch import render_and_write_daily_file
from app.services.photo_storage import delete_photo, resize_image, save_photo


class PhotoService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def update_meal_time(
        self, photo_id: int, meal_time: datetime.datetime
    ) -> Photo:
        photo = (
            await self.db.execute(select(Photo).where(Photo.id == photo_id))
        ).scalar_one_or_none()
        if photo is None:
            raise NotFoundError(f"Photo {photo_id} not found")
        photo.meal_time = meal_time
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
            await self.db.execute(select(Entry).where(Entry.date == entry_date))
        ).scalar_one_or_none()
        if entry is None:
            raise NotFoundError(f"No entry for {entry_date}")

        # Determine next photo number via max(existing)+1 to avoid collision
        # after deletions. COUNT()+1 is wrong once any row is deleted.
        prefix = f"{entry_date.isoformat()}_photo-"
        suffix = ".jpg"
        used_numbers: set[int] = set()
        rows = (
            await self.db.execute(
                select(Photo.filename).where(Photo.entry_id == entry.id)
            )
        ).all()
        for (existing_filename,) in rows:
            if existing_filename.startswith(prefix) and existing_filename.endswith(
                suffix
            ):
                try:
                    used_numbers.add(int(existing_filename[len(prefix) : -len(suffix)]))
                except ValueError:
                    pass
        photo_number = max(used_numbers, default=0) + 1
        filename = f"{prefix}{photo_number}{suffix}"

        raw_bytes = await file.read()
        processed_bytes = await asyncio.to_thread(resize_image, raw_bytes)
        await asyncio.to_thread(
            save_photo, processed_bytes, filename, settings.vault_path
        )

        now = datetime.datetime.utcnow()
        photo = Photo(
            entry_id=entry.id,
            filename=filename,
            label=label,
            original_filename=file.filename,
            meal_time=meal_time if meal_time is not None else now,
            created_at=now,
        )
        self.db.add(photo)
        await self.db.commit()
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
