from __future__ import annotations

import datetime
import uuid
from typing import Optional

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.till_basket import TillBasket
from f0rge_db.crud import BaseCRUD
from f0rge_db.organisation import tenant_id_ctx


class TillBasketCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def owned(
        self,
        user_id: uuid.UUID,
        *,
        basket_id: Optional[uuid.UUID] = None,
        location_id: Optional[uuid.UUID] = None,
        lock: bool = False,
    ) -> Optional[TillBasket]:
        query = select(TillBasket).where(
            TillBasket.team_id == tenant_id_ctx.get(), TillBasket.user_id == user_id
        )
        if basket_id is not None:
            query = query.where(TillBasket.id == basket_id)
        if location_id is not None:
            query = query.where(TillBasket.location_id == location_id)
        if lock:
            query = query.with_for_update().execution_options(populate_existing=True)
        return await self.db.scalar(query)

    async def ensure(self, user_id: uuid.UUID, location_id: uuid.UUID) -> None:
        """Insert the empty basket unless a concurrent caller already did."""
        await self.db.execute(
            pg_insert(TillBasket)
            .values(
                id=uuid.uuid4(),
                team_id=tenant_id_ctx.get(),
                location_id=location_id,
                user_id=user_id,
                linked_pick_ids={},
                lines=[],
            )
            .on_conflict_do_nothing(index_elements=["team_id", "location_id", "user_id"])
        )

    async def empty_expired(self, now: datetime.datetime) -> None:
        """Empty the tenant's expired baskets in one statement, skipping rows being edited."""
        due = (
            select(TillBasket.id)
            .where(
                TillBasket.team_id == tenant_id_ctx.get(),
                TillBasket.expires_at <= now,
                func.jsonb_array_length(TillBasket.lines) > 0,
            )
            .order_by(TillBasket.id)
            .with_for_update(skip_locked=True)
        )
        await self.db.execute(
            update(TillBasket)
            .where(TillBasket.id.in_(due))
            .values(
                expired_at=TillBasket.expires_at,
                expires_at=None,
                lines=[],
                customer_id=None,
                note=None,
                note_printed=None,
                note_internal=None,
                sales_staff_id=None,
                quote_id=None,
                pick_id=None,
                linked_pick_ids={},
                last_operation_id=None,
                version=TillBasket.version + 1,
                updated_at=now,
            )
            .execution_options(synchronize_session=False)
        )
