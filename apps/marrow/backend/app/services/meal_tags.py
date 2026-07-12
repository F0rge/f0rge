from __future__ import annotations

import datetime
import json
import uuid
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import unit_of_work
from app.crud.meal_tags import MealTagCRUD
from app.crud.social import SocialCRUD
from app.models.meal_tag import MealTag
from app.models.photo import Photo
from f0rge_core.exceptions import ConflictError, NotFoundError, ValidationError
from app.schemas.social import (
    IncomingMealTagItem,
    MealTagListResponse,
    OutgoingMealTagItem,
    PublicUserCard,
    validate_handle_format,
)
from app.services.social import SocialService
from app.services.tag_delivery import TagDeliveryService
from f0rge_db.tenant import current_user_id

MAX_TAGS_PER_MEAL = 10


class MealTagService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = MealTagCRUD(db)
        self.social_crud = SocialCRUD(db)
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

    async def create_tags_for_photo(
        self,
        photo: Photo,
        entry_date: datetime.date,
        tagged_handles_raw: Optional[str],
        *,
        analysis_will_run: bool,
    ) -> None:
        handles = self.parse_tagged_handles(tagged_handles_raw)
        if not handles:
            return

        me = current_user_id()
        seen: set[str] = set()
        recipients: list[uuid.UUID] = []

        for handle in handles:
            if handle in seen:
                continue
            seen.add(handle)
            user = await self.social_crud.get_by_handle(handle)
            if user is None or user.handle is None:
                raise NotFoundError(f"No user with handle @{handle}")
            if user.id == me:
                raise ValidationError("You cannot tag yourself")
            await SocialService(self.db).assert_connected(user.id)
            recipients.append(user.id)

        if len(recipients) > MAX_TAGS_PER_MEAL:
            raise ValidationError(f"At most {MAX_TAGS_PER_MEAL} tags per meal")

        async with unit_of_work(self.db):
            for recipient_id in recipients:
                tag = MealTag(
                    source_photo_id=photo.id,
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

        if not analysis_will_run:
            await self.delivery.process_photo_only_source(photo.id, me)

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
        async with unit_of_work(self.db):
            await self.crud.flush()

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
