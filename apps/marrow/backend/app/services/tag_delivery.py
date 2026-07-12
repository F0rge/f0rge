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
from app.crud.photo_ingredient import PhotoIngredientCRUD
from app.crud.photos import PhotoCRUD
from app.crud.settings import UserSettingsCRUD
from app.database import async_session_maker
from app.models.meal_tag import MealTag
from app.models.photo import Photo
from app.models.photo_analysis import PhotoAnalysis
from app.models.photo_ingredient import PhotoIngredient
from app.services.entries import get_or_create_entry
from app.services.notifications import NotificationService
from app.services.photo_storage import delete_photo, photo_exists, read_photo, save_photo
from app.services.photos import next_photo_filename
from f0rge_core.exceptions import NotFoundError
from f0rge_db.tenant import apply_session_user_id, clear_tenant_session


class TagDeliveryService:
    """Cross-user meal delivery for social tagging.

    State machine (single source of truth):

    | From | Event | To | Side effects |
    | --- | --- | --- | --- |
    | — | tagger uploads meal with tags | pending_analysis | snapshot source_label, source_date |
    | pending_analysis | source analysis confirmed (or photo-only) | auto → delivered; approve → pending_approval | snapshot source_dish_name; notify |
    | pending_approval | recipient approves | delivered | deliver copy (no notify) |
    | pending_approval | recipient declines | declined | row kept |
    | pending_analysis / pending_approval | tagger cancels | cancelled | — |
    | pending_analysis / pending_approval | connection removed | cancelled | — |
    """

    async def deliver_for_source(self, source_photo_id: int, tagger_id: uuid.UUID) -> None:
        """Entry after analysis confirm — fresh session per call."""
        async with async_session_maker() as db:
            try:
                await apply_session_user_id(db, tagger_id)
                crud = MealTagCRUD(db)
                tags = await crud.list_pending_analysis_for_source(source_photo_id)
                if not tags:
                    return
                dish_name = await self._load_confirmed_dish_name(db, tagger_id, source_photo_id)
                await self._transition_pending_analysis(db, tags, dish_name)
                await db.commit()
            finally:
                await clear_tenant_session(db)

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
                await apply_session_user_id(db, tagger_id)
                crud = MealTagCRUD(db)
                tags = await crud.list_pending_analysis_for_source(source_photo_id)
                if not tags:
                    return
                await self._transition_pending_analysis(db, tags, dish_name=None)
                await db.commit()
            finally:
                await clear_tenant_session(db)

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
        if not photo_exists(source_photo.filename, user_id=tagger_id_str):
            raise NotFoundError(f"Source photo file missing for tag {tag.id}")

        src_bytes = await asyncio.to_thread(
            read_photo, source_photo.filename, user_id=tagger_id_str
        )
        analysis_crud = PhotoAnalysisCRUD(db)
        src_analysis = await analysis_crud.get_by_photo_id_with_ingredients(tag.source_photo_id)
        has_confirmed = src_analysis is not None and src_analysis.status == "confirmed"

        # Step 2: clone under the recipient's tenant context.
        await apply_session_user_id(db, tag.tagged_user_id)
        recipient_id = tag.tagged_user_id
        recipient_id_str = str(recipient_id)

        entry = await get_or_create_entry(db, tag.source_date)
        new_filename = await next_photo_filename(db, entry)
        now = datetime.datetime.utcnow()

        new_photo = Photo(
            user_id=recipient_id,
            entry_id=entry.id,
            filename=new_filename,
            label=source_photo.label,
            original_filename=source_photo.original_filename,
            meal_time=source_photo.meal_time or now,
            source_photo_id=source_photo.id,
            tagged_by_user_id=tag.tagger_id,
            created_at=now,
        )
        photo_crud = PhotoCRUD(db)
        ingredient_crud = PhotoIngredientCRUD(db)

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

        try:
            await photo_crud.add_and_flush(new_photo)

            if has_confirmed and src_analysis is not None:
                new_analysis = PhotoAnalysis(
                    user_id=recipient_id,
                    photo_id=new_photo.id,
                    status="confirmed",
                    dish_name=src_analysis.dish_name,
                    cuisine=src_analysis.cuisine,
                    dish_confidence=src_analysis.dish_confidence,
                    model_id=src_analysis.model_id,
                    raw_response=src_analysis.raw_response,
                    gluten_free_confirmed=src_analysis.gluten_free_confirmed,
                    lactose_free_confirmed=src_analysis.lactose_free_confirmed,
                )
                await analysis_crud.add_and_flush(new_analysis)
                for si in src_analysis.ingredients:
                    ingredient_crud.add(
                        PhotoIngredient(
                            user_id=recipient_id,
                            analysis_id=new_analysis.id,
                            name=si.name,
                            canonical_name=si.canonical_name,
                            visible=si.visible,
                            confidence=si.confidence,
                            user_edited=si.user_edited,
                            histamine_score=si.histamine_score,
                            fodmap_oligos=si.fodmap_oligos,
                            fodmap_fructose=si.fodmap_fructose,
                            fodmap_polyols=si.fodmap_polyols,
                            fodmap_lactose=si.fodmap_lactose,
                            contains_gluten=si.contains_gluten,
                            contains_dairy=si.contains_dairy,
                        )
                    )

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

    async def _load_confirmed_dish_name(
        self, db: AsyncSession, tagger_id: uuid.UUID, source_photo_id: int
    ) -> Optional[str]:
        await apply_session_user_id(db, tagger_id)
        analysis = await PhotoAnalysisCRUD(db).get_by_photo_id(source_photo_id)
        if analysis is None or analysis.status != "confirmed":
            return None
        return analysis.dish_name

    async def _load_handle(self, db: AsyncSession, user_id: uuid.UUID) -> Optional[str]:
        from app.models.user import User

        row = await db.get(User, user_id)
        return row.handle if row is not None else None
