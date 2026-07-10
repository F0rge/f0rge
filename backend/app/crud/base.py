from __future__ import annotations

import datetime
from typing import Generic, Iterable, Optional, Type, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.tenant import owned_by_user

# Shared across every Batch-A CRUD class: add/commit/refresh/delete are the
# same three lines everywhere. #225 will revisit commit/refresh semantics
# (unit-of-work); until then this preserves the exact call sequence each
# service used to run inline.
M = TypeVar("M")


class BaseCRUD:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    def add(self, obj: object) -> None:
        self.db.add(obj)

    async def flush(self) -> None:
        await self.db.flush()

    async def commit(self) -> None:
        await self.db.commit()

    async def refresh(self, obj: object) -> None:
        await self.db.refresh(obj)

    async def add_and_flush(self, obj: M) -> M:
        self.db.add(obj)
        await self.db.flush()
        return obj

    async def commit_refresh(self, obj: M) -> M:
        await self.db.commit()
        await self.db.refresh(obj)
        return obj

    async def delete_and_commit(self, obj: object) -> None:
        await self.db.delete(obj)
        await self.db.commit()


# Symptom/supplement/medication/diet-tag catalogs are the same table shape
# (key, label, sort_order, archived, [first_used_at, last_used_at]) with only
# the model class and the user-scoping differing. Genuinely shared, not
# speculative — 4 near-identical ~100-line services collapse to this.
class CatalogItemCRUD(BaseCRUD, Generic[M]):
    def __init__(self, db: AsyncSession, model: Type[M], *, user_scoped: bool) -> None:
        super().__init__(db)
        self.model = model
        self.user_scoped = user_scoped

    def _scope(self, stmt):
        return stmt.where(owned_by_user(self.model.user_id)) if self.user_scoped else stmt

    async def list(self, include_archived: bool = False) -> list[M]:
        stmt = self._scope(select(self.model))
        if not include_archived:
            stmt = stmt.where(self.model.archived.is_(False))
        stmt = stmt.order_by(self.model.sort_order.asc(), self.model.id.asc())
        return list((await self.db.execute(stmt)).scalars().all())

    async def get_by_key(self, key: str) -> Optional[M]:
        stmt = self._scope(select(self.model).where(self.model.key == key))
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_max_sort_order_item(self) -> Optional[M]:
        stmt = self._scope(select(self.model)).order_by(self.model.sort_order.desc())
        return (await self.db.execute(stmt)).scalars().first()

    async def touch(self, keys: Iterable[str]) -> None:
        """Bulk-update first_used_at/last_used_at. Caller owns the transaction."""
        key_list = list(keys)
        if not key_list:
            return
        now = datetime.datetime.utcnow()
        stmt = self._scope(select(self.model).where(self.model.key.in_(key_list)))
        existing = {item.key: item for item in (await self.db.execute(stmt)).scalars().all()}
        for key in key_list:
            item = existing.get(key)
            if item is None:
                continue
            if item.first_used_at is None:
                item.first_used_at = now
            item.last_used_at = now
