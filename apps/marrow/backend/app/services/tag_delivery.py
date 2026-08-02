from __future__ import annotations

import asyncio
import datetime
import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.meal_tags import MealTagCRUD
from app.crud.photo_analysis import PhotoAnalysisCRUD
from app.crud.photos import PhotoCRUD
from app.crud.settings import UserSettingsCRUD
from app.database import async_session_maker
from app.models.meal_tag import MealTag
from app.models.photo import Photo
from app.services.entries import get_or_create_entry
from app.services.notifications import NotificationService
from app.services.photo_storage import delete_photo, photo_exists, read_photo, save_photo
from app.services.photos import next_photo_filename
from f0rge_core.exceptions import NotFoundError
from f0rge_db.tenant import apply_session_user_id, clear_tenant_session


class TagDeliveryService:
    """Cross-user meal delivery for social tagging.

    Delivered copies are entry **placements** pointing at the tagger's canonical
    ``meal_id`` — analysis is shared, not cloned per recipient.
    """

    async def deliver_for_source(self, source_photo_id: int, tagger_id: uuid.UUID) -> None:
        """Entry after analysis confirm — fresh session per call."""
        async with async_session_maker() as db:
            try:
                await self.deliver_for_source_in_transaction(db, source_photo_id, tagger_id)
                await db.commit()
            finally:
                await clear_tenant_session(db)

    async def deliver_for_source_in_transaction(
        self, db: AsyncSession, source_photo_id: int, tagger_id: uuid.UUID
    ) -> None:
        """Deliver pending tags using the caller's session; caller owns commit/rollback."""
        await apply_session_user_id(db, tagger_id)
        await self._deliver_pending_analysis_for_source(
            db, tagger_id, source_photo_id, load_dish_name=True
        )
        await self._sync_dish_name_to_open_tags(db, tagger_id, source_photo_id)

    async def _sync_dish_name_to_open_tags(
        self, db: AsyncSession, tagger_id: uuid.UUID, source_photo_id: int
    ) -> None:
        """Refresh ``source_dish_name`` on tags already awaiting approval or delivered."""
        dish_name = await self._load_dish_name(db, tagger_id, source_photo_id)
        if not dish_name:
            return
        stmt = select(MealTag).where(
            MealTag.source_photo_id == source_photo_id,
            MealTag.status.in_(("pending_approval", "delivered")),
        )
        for tag in (await db.execute(stmt)).scalars().all():
            tag.source_dish_name = dish_name
        await db.flush()

    async def deliver_one(self, tag_id: uuid.UUID, recipient_id: uuid.UUID) -> None:
        """Synchronous approve path — delivers a single pending_approval tag."""
        async with async_session_maker() as db:
            try:
                await apply_session_user_id(db, recipient_id)
                tag = await MealTagCRUD(db).get_by_id_for_user(tag_id)
                if tag is None or tag.status != "pending_approval":
                    raise NotFoundError("Meal tag not found")
                await self._deliver_tag(db, tag, notify=False)
                await db.commit()
            finally:
                await clear_tenant_session(db)

    async def process_photo_only_source(self, source_photo_id: int, tagger_id: uuid.UUID) -> None:
        """When analysis pipeline won't run, transition tags immediately (photo-only)."""
        async with async_session_maker() as db:
            try:
                await self.process_photo_only_source_in_transaction(db, source_photo_id, tagger_id)
                await db.commit()
            finally:
                await clear_tenant_session(db)

    async def process_photo_only_source_in_transaction(
        self, db: AsyncSession, source_photo_id: int, tagger_id: uuid.UUID
    ) -> None:
        """Photo-only tag delivery using the caller's session; caller owns commit/rollback."""
        await apply_session_user_id(db, tagger_id)
        await self._deliver_pending_analysis_for_source(
            db, tagger_id, source_photo_id, load_dish_name=False
        )

    async def _deliver_pending_analysis_for_source(
        self,
        db: AsyncSession,
        tagger_id: uuid.UUID,
        source_photo_id: int,
        *,
        load_dish_name: bool,
    ) -> None:
        crud = MealTagCRUD(db)
        tags = await crud.list_pending_analysis_for_source(source_photo_id)
        if not tags:
            return
        dish_name: Optional[str] = None
        if load_dish_name:
            dish_name = await self._load_dish_name(db, tagger_id, source_photo_id)
        await self._transition_pending_analysis(db, tags, dish_name)

    async def _transition_pending_analysis(
        self,
        db: AsyncSession,
        tags: list[MealTag],
        dish_name: Optional[str],
    ) -> None:
        notifications = NotificationService(db)
        settings_crud = UserSettingsCRUD(db)

        for tag in tags:
            tag.source_dish_name = dish_name
            await apply_session_user_id(db, tag.tagged_user_id)
            settings = await settings_crud.get()
            mode = settings.tagged_meal_mode if settings is not None else "approve"

            if mode == "auto":
                await self._deliver_tag(db, tag, notify=True, notifications=notifications)
            else:
                tag.status = "pending_approval"
                tagger_handle = await self._load_handle(db, tag.tagger_id)
                await notifications.notify(
                    tag.tagged_user_id,
                    "meal_tag_request",
                    {
                        "handle": tagger_handle or "",
                        "dish_name": dish_name or tag.source_label,
                        "date": tag.source_date.isoformat(),
                        "tag_id": str(tag.id),
                    },
                )

    async def _deliver_tag(
        self,
        db: AsyncSession,
        tag: MealTag,
        *,
        notify: bool,
        notifications: Optional[NotificationService] = None,
    ) -> None:
        if tag.status == "delivered" and tag.delivered_photo_id is not None:
            return

        # Step 1: read source rows under the tagger's tenant context.
        await apply_session_user_id(db, tag.tagger_id)
        source_photo = await PhotoCRUD(db).get_by_id(tag.source_photo_id)
        if source_photo is None:
            raise NotFoundError(f"Source photo {tag.source_photo_id} not found for tag {tag.id}")

        tagger_id_str = str(tag.tagger_id)
        # Library / icon-only meals have no bytes to copy to the recipient.
        if not source_photo.filename or not photo_exists(
            source_photo.filename, user_id=tagger_id_str
        ):
            raise NotFoundError(f"Source photo file missing for tag {tag.id}")

        src_bytes = await asyncio.to_thread(
            read_photo, source_photo.filename, user_id=tagger_id_str
        )

        # Step 2: create recipient placement (same meal_id) under recipient context.
        await apply_session_user_id(db, tag.tagged_user_id)
        recipient_id = tag.tagged_user_id
        recipient_id_str = str(recipient_id)

        entry = await get_or_create_entry(db, tag.source_date)
        new_filename = await next_photo_filename(db, entry)
        now = datetime.datetime.utcnow()

        photo_crud = PhotoCRUD(db)

        existing = (
            await db.execute(
                select(Photo).where(
                    Photo.user_id == recipient_id,
                    Photo.source_photo_id == source_photo.id,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            tag.status = "delivered"
            tag.delivered_photo_id = existing.id
            tag.resolved_at = now
            await db.flush()
            return

        new_photo = Photo(
            user_id=recipient_id,
            entry_id=entry.id,
            meal_id=source_photo.meal_id,
            filename=new_filename,
            label=source_photo.label,
            original_filename=source_photo.original_filename,
            meal_time=source_photo.meal_time or now,
            source_photo_id=source_photo.id,
            tagged_by_user_id=tag.tagger_id,
            created_at=now,
        )

        try:
            await photo_crud.add_and_flush(new_photo)
            await asyncio.to_thread(save_photo, src_bytes, new_filename, user_id=recipient_id_str)

            tag.status = "delivered"
            tag.delivered_photo_id = new_photo.id
            tag.resolved_at = now
            await db.flush()

            if notify:
                notif = notifications or NotificationService(db)
                tagger_handle = await self._load_handle(db, tag.tagger_id)
                await notif.notify(
                    tag.tagged_user_id,
                    "meal_tag_delivered",
                    {
                        "handle": tagger_handle or "",
                        "dish_name": tag.source_dish_name or tag.source_label,
                        "date": tag.source_date.isoformat(),
                        "tag_id": str(tag.id),
                    },
                )
        except IntegrityError:
            await asyncio.to_thread(delete_photo, new_filename, user_id=recipient_id_str)
            dup = (
                await db.execute(
                    select(Photo).where(
                        Photo.user_id == recipient_id,
                        Photo.source_photo_id == source_photo.id,
                    )
                )
            ).scalar_one_or_none()
            if dup is not None:
                tag.status = "delivered"
                tag.delivered_photo_id = dup.id
                tag.resolved_at = now
                await db.flush()
            else:
                raise
        except Exception:
            await asyncio.to_thread(delete_photo, new_filename, user_id=recipient_id_str)
            raise

    async def sync_confirmed_analysis_to_copies(
        self, db: AsyncSession, source_photo_id: int, tagger_id: uuid.UUID
    ) -> None:
        """No-op: analysis is meal-scoped; copies share ``meal_id``."""

    async def _load_dish_name(
        self, db: AsyncSession, tagger_id: uuid.UUID, source_photo_id: int
    ) -> Optional[str]:
        await apply_session_user_id(db, tagger_id)
        analysis = await PhotoAnalysisCRUD(db).get_for_photo_with_ingredients(source_photo_id)
        if analysis is None:
            return None
        return analysis.dish_name

    async def _load_handle(self, db: AsyncSession, user_id: uuid.UUID) -> Optional[str]:
        from app.models.user import User

        row = await db.get(User, user_id)
        return row.handle if row is not None else None
