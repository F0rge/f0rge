from __future__ import annotations

import datetime
import json
import uuid
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import unit_of_work
from app.crud.groups import GroupCRUD
from app.crud.meal_tags import MealTagCRUD
from app.crud.photo_analysis import PhotoAnalysisCRUD
from app.crud.photos import PhotoCRUD
from app.crud.social import SocialCRUD
from app.models.meal_tag import MealTag
from app.models.photo import Photo
from f0rge_core.exceptions import ConflictError, NotFoundError, ValidationError
from app.schemas.social import (
    IncomingMealTagItem,
    MealTagListResponse,
    OutgoingMealTagItem,
    PhotoMealTagItem,
    PhotoMealTagListResponse,
    PublicUserCard,
    validate_handle_format,
)
from app.services.social import SocialService
from app.services.notifications import NotificationService
from app.services.tag_delivery import TagDeliveryService
from f0rge_db.tenant import apply_session_user_id, current_user_id

MAX_TAGS_PER_MEAL = 10


class MealTagService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = MealTagCRUD(db)
        self.social_crud = SocialCRUD(db)
        self.group_crud = GroupCRUD(db)
        self.delivery = TagDeliveryService()

    @staticmethod
    def parse_tagged_handles(raw: Optional[str]) -> list[str]:
        if raw is None or raw.strip() == "":
            return []
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValidationError("tagged_handles must be a JSON array string") from exc
        if not isinstance(parsed, list):
            raise ValidationError("tagged_handles must be a JSON array")
        if not all(isinstance(item, str) for item in parsed):
            raise ValidationError("tagged_handles must contain only strings")
        if len(parsed) > MAX_TAGS_PER_MEAL:
            raise ValidationError(f"At most {MAX_TAGS_PER_MEAL} tags per meal")
        return [validate_handle_format(h) for h in parsed]

    @staticmethod
    def parse_tagged_group_ids(raw: Optional[str]) -> list[uuid.UUID]:
        if raw is None or raw.strip() == "":
            return []
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValidationError("tagged_group_ids must be a JSON array string") from exc
        if not isinstance(parsed, list):
            raise ValidationError("tagged_group_ids must be a JSON array")
        if not all(isinstance(item, str) for item in parsed):
            raise ValidationError("tagged_group_ids must contain only UUID strings")
        if len(parsed) > MAX_TAGS_PER_MEAL:
            raise ValidationError(f"At most {MAX_TAGS_PER_MEAL} groups per meal")
        try:
            return [uuid.UUID(item) for item in parsed]
        except ValueError as exc:
            raise ValidationError("tagged_group_ids must contain valid UUIDs") from exc

    async def _recipients_for_handles(self, handles: list[str]) -> list[uuid.UUID]:
        if not handles:
            return []

        me = current_user_id()
        seen: set[str] = set()
        recipients: list[uuid.UUID] = []
        social = SocialService(self.db)

        for handle in handles:
            if handle in seen:
                continue
            seen.add(handle)
            user = await self.social_crud.get_by_handle(handle)
            if user is None or user.handle is None:
                raise NotFoundError(f"No user with handle @{handle}")
            if user.id == me:
                raise ValidationError("You cannot tag yourself")
            await social.assert_connected(user.id)
            recipients.append(user.id)

        return recipients

    async def _recipients_for_groups(self, group_ids: list[uuid.UUID]) -> list[uuid.UUID]:
        if not group_ids:
            return []

        me = current_user_id()
        seen: set[uuid.UUID] = set()
        recipients: list[uuid.UUID] = []
        social = SocialService(self.db)

        for group_id in group_ids:
            membership = await self.group_crud.get_my_membership(group_id)
            if membership is None or membership.status != "joined":
                raise NotFoundError("Group not found")

            for member, user in await self.group_crud.list_members_with_users(group_id):
                if member.status != "joined" or user.id == me:
                    continue
                if user.id in seen:
                    continue
                try:
                    await social.assert_connected(user.id)
                except ValidationError:
                    continue
                seen.add(user.id)
                recipients.append(user.id)

        return recipients

    async def _merge_recipients(
        self,
        handle_recipients: list[uuid.UUID],
        group_recipients: list[uuid.UUID],
    ) -> list[uuid.UUID]:
        merged: list[uuid.UUID] = []
        seen: set[uuid.UUID] = set()
        for recipient_id in [*handle_recipients, *group_recipients]:
            if recipient_id in seen:
                continue
            seen.add(recipient_id)
            merged.append(recipient_id)
        if len(merged) > MAX_TAGS_PER_MEAL:
            raise ValidationError(f"At most {MAX_TAGS_PER_MEAL} tags per meal")
        return merged

    async def resolve_tagged_recipients(
        self,
        tagged_handles_raw: Optional[str] = None,
        tagged_group_ids_raw: Optional[str] = None,
    ) -> list[uuid.UUID]:
        handles = self.parse_tagged_handles(tagged_handles_raw)
        group_ids = self.parse_tagged_group_ids(tagged_group_ids_raw)
        handle_recipients = await self._recipients_for_handles(handles)
        group_recipients = await self._recipients_for_groups(group_ids)
        return await self._merge_recipients(handle_recipients, group_recipients)

    async def insert_tags_for_photo(
        self,
        photo: Photo,
        entry_date: datetime.date,
        recipients: list[uuid.UUID],
    ) -> None:
        me = current_user_id()
        for recipient_id in recipients:
            existing = await self.crud.get_for_source_and_recipient(photo.id, recipient_id)
            if existing is not None:
                if existing.status == "cancelled":
                    existing.status = "pending_analysis"
                    existing.resolved_at = None
                    existing.source_meal_id = photo.meal_id
                    existing.source_label = photo.label
                    existing.source_date = entry_date
                    await self.crud.flush()
                    continue
                if existing.status == "declined":
                    raise ConflictError("This user declined the meal tag")
                raise ConflictError("This meal was already tagged for that user")

            tag = MealTag(
                source_photo_id=photo.id,
                source_meal_id=photo.meal_id,
                tagger_id=me,
                tagged_user_id=recipient_id,
                status="pending_analysis",
                source_label=photo.label,
                source_date=entry_date,
            )
            try:
                await self.crud.add_tag(tag)
            except IntegrityError as exc:
                raise ConflictError("This meal was already tagged for that user") from exc

    async def create_tags_for_photo(
        self,
        photo: Photo,
        entry_date: datetime.date,
        tagged_handles_raw: Optional[str],
        *,
        tagged_group_ids_raw: Optional[str] = None,
        analysis_will_run: bool,
    ) -> None:
        recipients = await self.resolve_tagged_recipients(tagged_handles_raw, tagged_group_ids_raw)
        if not recipients:
            return

        me = current_user_id()
        async with unit_of_work(self.db):
            await self.insert_tags_for_photo(photo, entry_date, recipients)

        await self.delivery.process_photo_only_source(photo.id, me)
        await apply_session_user_id(self.db, me)

    async def list_tags(self) -> MealTagListResponse:
        incoming: list[IncomingMealTagItem] = []
        for tag in await self.crud.list_incoming_pending():
            tagger = await self.social_crud.get_by_id(tag.tagger_id)
            incoming.append(
                IncomingMealTagItem(
                    id=tag.id,
                    tagger=SocialService.to_public_card(tagger)
                    if tagger
                    else PublicUserCard(handle="", avatar_default_index=0),
                    source_dish_name=tag.source_dish_name,
                    source_label=tag.source_label,
                    source_date=tag.source_date,
                    created_at=tag.created_at,
                )
            )

        outgoing: list[OutgoingMealTagItem] = []
        for tag in await self.crud.list_outgoing():
            tagged = await self.social_crud.get_by_id(tag.tagged_user_id)
            outgoing.append(
                OutgoingMealTagItem(
                    id=tag.id,
                    tagged_user=SocialService.to_public_card(tagged)
                    if tagged
                    else PublicUserCard(handle="", avatar_default_index=0),
                    status=tag.status,
                    source_dish_name=tag.source_dish_name,
                    source_label=tag.source_label,
                    source_date=tag.source_date,
                    created_at=tag.created_at,
                )
            )

        return MealTagListResponse(incoming_pending=incoming, outgoing=outgoing)

    async def approve(self, tag_id: uuid.UUID) -> None:
        me = current_user_id()
        tag = await self.crud.get_by_id_for_user(tag_id)
        if tag is None:
            raise NotFoundError("Meal tag not found")
        if tag.tagged_user_id != me:
            raise ValidationError("Only the recipient can approve")
        if tag.status != "pending_approval":
            raise ValidationError("Tag is not awaiting approval")
        await self.delivery.deliver_one(tag_id, me)
        notifications = NotificationService(self.db)
        async with unit_of_work(self.db):
            await notifications.mark_resolved("meal_tag_request", "tag_id", str(tag_id))

    async def decline(self, tag_id: uuid.UUID) -> None:
        me = current_user_id()
        tag = await self.crud.get_by_id_for_user(tag_id)
        if tag is None:
            raise NotFoundError("Meal tag not found")
        if tag.tagged_user_id != me:
            raise ValidationError("Only the recipient can decline")
        if tag.status != "pending_approval":
            raise ValidationError("Tag is not awaiting approval")
        tag.status = "declined"
        tag.resolved_at = datetime.datetime.utcnow()
        notifications = NotificationService(self.db)
        async with unit_of_work(self.db):
            await self.crud.flush()
            await notifications.mark_resolved("meal_tag_request", "tag_id", str(tag_id))

    async def cancel(self, tag_id: uuid.UUID) -> None:
        me = current_user_id()
        tag = await self.crud.get_by_id_for_user(tag_id)
        if tag is None:
            raise NotFoundError("Meal tag not found")
        if tag.tagger_id != me:
            raise ValidationError("Only the tagger can cancel")
        if tag.status not in ("pending_analysis", "pending_approval"):
            raise ValidationError("Only pending tags can be cancelled")
        tag.status = "cancelled"
        tag.resolved_at = datetime.datetime.utcnow()
        async with unit_of_work(self.db):
            await self.crud.flush()

    async def cancel_pending_for_connection(self, user_a: uuid.UUID, user_b: uuid.UUID) -> None:
        await self.crud.cancel_pending_between_users(user_a, user_b)

    async def list_tags_for_photo(self, photo_id: int) -> PhotoMealTagListResponse:
        photo = await PhotoCRUD(self.db).get_by_id_owned(photo_id)
        if photo is None:
            raise NotFoundError("Photo not found")
        me = current_user_id()
        await apply_session_user_id(self.db, me)
        return await self._tags_response_for_photo(photo_id)

    async def add_tags_to_photo(
        self,
        photo_id: int,
        handles: list[str],
        group_ids: list[uuid.UUID] | None = None,
    ) -> PhotoMealTagListResponse:
        photo_crud = PhotoCRUD(self.db)
        photo = await photo_crud.get_by_id_owned(photo_id)
        if photo is None:
            raise NotFoundError("Photo not found")
        if photo.source_photo_id is not None:
            raise ValidationError("You can only tag people on meals you logged yourself")

        normalized_handles = self._normalize_handle_list(handles)
        normalized_groups = list(group_ids or [])
        if not normalized_handles and not normalized_groups:
            raise ValidationError("At least one handle or group_id is required")

        me = current_user_id()
        existing_ids = set(await self.crud.list_tagged_user_ids_for_source(photo_id))
        handle_recipients = await self._recipients_for_handles(normalized_handles)
        group_recipients = await self._recipients_for_groups(normalized_groups)
        merged = await self._merge_recipients(handle_recipients, group_recipients)
        new_recipients = [uid for uid in merged if uid not in existing_ids]

        if len(existing_ids) + len(new_recipients) > MAX_TAGS_PER_MEAL:
            raise ValidationError(f"At most {MAX_TAGS_PER_MEAL} tags per meal")

        if new_recipients:
            entry_date = photo.entry.date
            async with unit_of_work(self.db):
                await self.insert_tags_for_photo(photo, entry_date, new_recipients)
            await apply_session_user_id(self.db, me)
            await self._deliver_new_tags_if_ready(photo_id, me)

        await apply_session_user_id(self.db, me)
        return await self._tags_response_for_photo(photo_id)

    @staticmethod
    def _normalize_handle_list(handles: list[str]) -> list[str]:
        if len(handles) > MAX_TAGS_PER_MEAL:
            raise ValidationError(f"At most {MAX_TAGS_PER_MEAL} tags per meal")
        return [validate_handle_format(h) for h in handles]

    async def _tags_response_for_photo(self, photo_id: int) -> PhotoMealTagListResponse:
        items: list[PhotoMealTagItem] = []
        for tag in await self.crud.list_for_source_photo(photo_id):
            tagged = await self.social_crud.get_by_id(tag.tagged_user_id)
            items.append(
                PhotoMealTagItem(
                    id=tag.id,
                    user=SocialService.to_public_card(tagged)
                    if tagged
                    else PublicUserCard(handle="", avatar_default_index=0),
                    status=tag.status,
                )
            )
        return PhotoMealTagListResponse(tags=items)

    async def _deliver_new_tags_if_ready(self, photo_id: int, tagger_id: uuid.UUID) -> None:
        analysis = await PhotoAnalysisCRUD(self.db).get_for_photo(photo_id)
        if analysis is not None and analysis.status == "confirmed":
            await self.delivery.deliver_for_source(photo_id, tagger_id)
        else:
            await self.delivery.process_photo_only_source(photo_id, tagger_id)
