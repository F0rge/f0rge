from __future__ import annotations

import datetime
from contextlib import asynccontextmanager
from typing import AsyncIterator, Generic, Iterable, Optional, Type, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.tenant import owned_by_user

M = TypeVar("M")


@asynccontextmanager
async def unit_of_work(db: AsyncSession) -> AsyncIterator[None]:
    """The one transaction boundary for every write path in ``app/crud`` and
    ``app/services`` (#225 Rule 6). Stage changes (``add``/``flush``/``delete``,
    no commit) inside ``async with unit_of_work(db): ...`` -- commits once on
    clean exit, rolls back once on exception. Never call ``db.commit()``
    directly outside this function.

    Gotcha (SQLAlchemy 2.x AsyncSession autobegin): a bare ``async with
    db.begin():`` raises ``InvalidRequestError: A transaction is already
    begun on this Session`` if a transaction is already open. In this app
    that's the common case, not the edge case -- ``get_db()`` calls
    ``apply_session_user_id()``, which runs ``SELECT set_config(...)`` for
    RLS before yielding the session to any service, so by the time a service
    method runs, ``db.in_transaction()`` is already True via autobegin.
    Branch on it: reuse the already-open transaction (commit/rollback it
    directly) when one exists, otherwise open one explicitly -- the latter
    only fires for a freshly-opened session with no prior query, e.g. a
    background task that builds its own session via ``async_session_maker()``
    and writes before ever reading.
    """
    if db.in_transaction():
        try:
            yield
            await db.commit()
        except Exception:
            await db.rollback()
            raise
    else:
        async with db.begin():
            yield


class BaseCRUD:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    def add(self, obj: object) -> None:
        self.db.add(obj)

    async def flush(self) -> None:
        await self.db.flush()

    async def refresh(self, obj: object) -> None:
        await self.db.refresh(obj)

    async def delete(self, obj: object) -> None:
        await self.db.delete(obj)

    async def add_and_flush(self, obj: M) -> M:
        self.db.add(obj)
        await self.db.flush()
        return obj

    async def save(self) -> None:
        """Commit the currently staged unit of work, no refresh."""
        async with unit_of_work(self.db):
            pass

    async def commit_refresh(self, obj: M) -> M:
        """Commit, then refresh ``obj``.

        Column values don't strictly need this refresh -- ``expire_on_commit
        =False`` app-wide (see ``app/database.py``) plus Postgres RETURNING
        already sync server-generated columns onto the instance during the
        flush ``commit()`` triggers. But several models expose ``lazy=
        "selectin"`` relationships in their response (``Entry.photos``,
        ``Lab.markers``, ``DietaryIngredient.aliases``, ...), and for an
        object that was *constructed* rather than loaded via a ``SELECT``,
        that eager companion query never ran -- the mapper only fires it
        while processing a query's results, not on later attribute access of
        an inserted-but-never-selected instance. A bare, unawaited attribute
        access then triggers an implicit lazy load outside the asyncpg
        greenlet bridge and raises ``MissingGreenlet``. ``refresh()`` (a real
        awaited DB round trip) safely (re)materializes everything up front.
        Auditing which of the 40-odd call sites truly never touch a
        relationship isn't worth the risk of missing one (#225 6.5: "keep it
        when in doubt" -- this was tried without refresh and broke labs/
        dietary-ingredient responses, see commit history).
        """
        await self.save()
        await self.db.refresh(obj)
        return obj

    async def delete_and_commit(self, obj: object) -> None:
        await self.db.delete(obj)
        await self.save()


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
