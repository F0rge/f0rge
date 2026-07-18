from __future__ import annotations

import asyncio
import datetime
import os
from typing import TYPE_CHECKING, Optional

from fastapi import BackgroundTasks, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.crud.base import unit_of_work
from app.crud.diet_tag_catalog import DietTagCatalogCRUD
from app.crud.entries import EntryCRUD
from app.crud.meals import MealCRUD
from app.crud.meal_tags import MealTagCRUD
from app.crud.photos import PhotoCRUD
from app.crud.settings import UserSettingsCRUD
from f0rge_core.exceptions import NotFoundError, ValidationError
from app.models.entry import Entry
from app.models.meal import Meal
from app.models.photo import Photo
from app.models.photo_diet_tag import PhotoDietTag
from app.schemas.photo import PhotoResponse, PhotoUpdate
from app.services.entries import _photo_response
from app.services import object_storage
from app.services.photo_storage import delete_photo, resize_image, save_photo
from f0rge_db.tenant import current_user_id

if TYPE_CHECKING:
    from app.services.food_analysis_orchestrator import FoodAnalysisOrchestrator
    from app.services.meal_tags import MealTagService


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
    for existing_filename in await PhotoCRUD(db).list_filenames_for_entry(entry.id):
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
    def __init__(
        self,
        db: AsyncSession,
        orchestrator: "FoodAnalysisOrchestrator",
        meal_tags: "MealTagService",
    ) -> None:
        self.db = db
        self.crud = PhotoCRUD(db)
        self.meal_crud = MealCRUD(db)
        self.entry_crud = EntryCRUD(db)
        self.settings_crud = UserSettingsCRUD(db)
        self.orchestrator = orchestrator
        self.meal_tags = meal_tags

    async def list_photos(
        self, scope: str, visibility: str, limit: int, offset: int
    ) -> list[PhotoResponse]:
        """Profile-grid feed: the user's photos, optionally only tagged copies.

        The profile tag-filter rule (settings) applies only to
        ``visibility="visible"``; hidden/all listings are never tag-filtered.
        """
        settings_row = await self.settings_crud.get() if visibility == "visible" else None
        mode = settings_row.profile_tag_filter_mode if settings_row else "off"
        filtering = mode != "off"
        photos = await self.crud.list_owned(
            tagged_only=scope == "tagged",
            visibility=visibility,
            limit=None if filtering else limit,
            offset=0 if filtering else offset,
        )
        companions = await MealTagCRUD(self.db).companion_handles_by_photo_ids(
            [p.id for p in photos]
        )
        # dish_name is set here rather than inside _photo_response because that
        # helper also serves the upload path, whose Photo is constructed in
        # Python: lazy="selectin" only fires at query time, so touching
        # .analysis on it would be implicit async IO (MissingGreenlet). These
        # photos come from a select(), so .analysis is already eager-loaded.
        responses: list[PhotoResponse] = []
        for p in photos:
            resp = _photo_response(p, companions.get(p.id, []))
            resp.dish_name = p.analysis.dish_name if p.analysis else None
            responses.append(resp)
        if filtering:
            # ponytail: in-Python tag filter + slice; move to SQL EXISTS if the
            # photo count ever makes this slow
            wanted = set(settings_row.profile_filter_tags_list)

            def _matches(r: PhotoResponse) -> bool:
                return bool((set(r.diet_tags) | set(r.derived_diet_tags)) & wanted)

            if mode == "hide":
                responses = [r for r in responses if not _matches(r)]
            else:  # show_only
                responses = [r for r in responses if _matches(r)]
            responses = responses[offset : offset + limit]
        return responses

    async def update_photo(self, photo_id: int, data: PhotoUpdate) -> PhotoResponse:
        photo = await self.crud.get_by_id_owned(photo_id)
        if photo is None:
            raise NotFoundError(f"Photo {photo_id} not found")

        fields = data.model_fields_set
        new_tags: Optional[list[str]] = None
        if data.diet_tags is not None:
            new_tags = sorted(set(data.diet_tags))
            known = {
                item.key for item in await DietTagCatalogCRUD(self.db).list(include_archived=True)
            }
            unknown = [key for key in new_tags if key not in known]
            if unknown:
                raise ValidationError(f"Unknown diet tag keys: {', '.join(unknown)}")

        if "label" in fields:
            # ""/whitespace clears the label so the UI falls back to the AI dish_name.
            stripped = data.label.strip() if data.label is not None else None
            photo.label = stripped or None
        if "meal_time" in fields:
            photo.meal_time = data.meal_time
        if data.hidden is not None:
            photo.hidden_at = datetime.datetime.utcnow() if data.hidden else None
        if new_tags is not None:
            # Replace the explicit tag set. user_id must be set explicitly —
            # the model default silently mis-owns rows for non-default users
            # under RLS (PR #359).
            # ponytail: replace-all delete+insert per PATCH; diff old vs new
            # keys if tag counts ever make this chatty
            photo.diet_tags = [
                PhotoDietTag(user_id=current_user_id(), photo_id=photo.id, key=key)
                for key in new_tags
            ]

        photo = await self.crud.commit_refresh(photo)
        # No companions lookup: mutation clients invalidate and refetch, so the
        # PATCH response keeps the pre-#403 tagged_with_handles=[] shape.
        return _photo_response(photo)

    async def upload(
        self,
        entry_date: datetime.date,
        file: UploadFile,
        label: Optional[str],
        meal_time: Optional[datetime.datetime],
        background_tasks: BackgroundTasks,
        tagged_handles: Optional[str] = None,
        tagged_group_ids: Optional[str] = None,
    ) -> PhotoResponse:
        entry = await self.entry_crud.get_by_date(entry_date)
        if entry is None:
            raise NotFoundError(f"No entry for {entry_date}")

        recipients = await self.meal_tags.resolve_tagged_recipients(
            tagged_handles, tagged_group_ids
        )

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

        effective_meal_time = normalized_meal_time if normalized_meal_time is not None else now
        user_id = current_user_id()

        # Invariant: a file on disk implies a DB row exists.
        # If the commit fails we clean up the file so the next upload
        # doesn't collide with a phantom on disk.
        meal = Meal(
            owner_user_id=user_id,
            filename=filename,
            label=label,
            original_filename=file.filename,
            meal_time=effective_meal_time,
            created_at=now,
        )
        photo = Photo(
            user_id=user_id,
            entry_id=entry.id,
            filename=filename,
            label=label,
            original_filename=file.filename,
            meal_time=effective_meal_time,
            created_at=now,
        )
        # Queue analysis when enabled and credentials resolve (env or BYOK).
        # Credential resolution must not fail the upload — the photo is already persisted.
        analysis_will_run = False
        if settings.food_analysis_enabled:
            from app.services.llm.factory import resolve_llm_credentials

            try:
                api_key, _ = await resolve_llm_credentials(self.db)
            except Exception:
                api_key = None
            if api_key:
                analysis_will_run = True

        try:
            async with unit_of_work(self.db):
                await self.meal_crud.add_and_flush(meal)
                photo.meal_id = meal.id
                self.crud.add(photo)
                await self.db.flush()
                if recipients:
                    await self.meal_tags.insert_tags_for_photo(photo, entry_date, recipients)
                if recipients:
                    await self.meal_tags.delivery.process_photo_only_source_in_transaction(
                        self.db, photo.id, user_id
                    )
        except Exception:
            await asyncio.to_thread(delete_photo, filename, user_id=str(user_id))
            raise

        if analysis_will_run:
            background_tasks.add_task(self.orchestrator.run, photo.id, photo.user_id)

        companions = await MealTagCRUD(self.db).companion_handles_by_photo_ids([photo.id])
        return _photo_response(photo, companions.get(photo.id, []))

    async def get_file_path(self, photo_id: int) -> str:
        photo = await self.crud.get_by_id_owned(photo_id)
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

    async def serve_photo_file(self, photo_id: int) -> FileResponse | RedirectResponse:
        target = await self.get_file_path(photo_id)
        if target.startswith("http://") or target.startswith("https://"):
            return RedirectResponse(target)
        return FileResponse(target, media_type="image/jpeg")

    async def delete(self, photo_id: int) -> None:
        photo = await self.crud.get_by_id_owned(photo_id)
        if photo is None:
            raise NotFoundError("Photo not found")
        filename = photo.filename
        meal_id = photo.meal_id
        user_id_str = str(photo.user_id)

        # Commit DB delete before touching the filesystem. If the commit fails,
        # no files are removed and the DB row remains — consistent state.
        await self.crud.delete_and_commit(photo)
        await self.meal_crud.delete_if_orphaned(meal_id)

        # File cleanup happens after the successful commit.
        await asyncio.to_thread(delete_photo, filename, user_id=user_id_str)
