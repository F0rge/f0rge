from __future__ import annotations

import datetime
import uuid
from typing import Optional

from sqlalchemy import and_, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import BaseCRUD
from app.models.meal_tag import MealTag
from f0rge_db.tenant import current_user_id


class MealTagCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_id_for_user(self, tag_id: uuid.UUID) -> Optional[MealTag]:
        me = current_user_id()
        stmt = select(MealTag).where(
            MealTag.id == tag_id,
            or_(MealTag.tagger_id == me, MealTag.tagged_user_id == me),
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def list_incoming_pending(self) -> list[MealTag]:
        me = current_user_id()
        stmt = (
            select(MealTag)
            .where(MealTag.tagged_user_id == me, MealTag.status == "pending_approval")
            .order_by(MealTag.created_at.desc())
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def list_outgoing(self) -> list[MealTag]:
        me = current_user_id()
        stmt = select(MealTag).where(MealTag.tagger_id == me).order_by(MealTag.created_at.desc())
        return list((await self.db.execute(stmt)).scalars().all())

    async def list_pending_analysis_for_source(self, source_photo_id: int) -> list[MealTag]:
        stmt = select(MealTag).where(
            MealTag.source_photo_id == source_photo_id,
            MealTag.status == "pending_analysis",
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def add_tag(self, tag: MealTag) -> MealTag:
        return await self.add_and_flush(tag)

    async def cancel_pending_between_users(self, user_a: uuid.UUID, user_b: uuid.UUID) -> None:
        now = datetime.datetime.utcnow()
        stmt = (
            update(MealTag)
            .where(
                MealTag.status.in_(("pending_analysis", "pending_approval")),
                or_(
                    and_(MealTag.tagger_id == user_a, MealTag.tagged_user_id == user_b),
                    and_(MealTag.tagger_id == user_b, MealTag.tagged_user_id == user_a),
                ),
            )
            .values(status="cancelled", resolved_at=now)
        )
        await self.db.execute(stmt)
