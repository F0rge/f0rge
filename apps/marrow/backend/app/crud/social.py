from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.auth import UserCRUD
from app.models.connection import Connection
from app.models.user import User
from app.schemas.social import normalize_handle
from f0rge_db.tenant import current_user_id


def _pair_ids(a: uuid.UUID, b: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID]:
    return (a, b) if a < b else (b, a)


class SocialCRUD(UserCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_handle(self, handle: str) -> Optional[User]:
        normalized = normalize_handle(handle)
        return (
            await self.db.execute(select(User).where(User.handle == normalized))
        ).scalar_one_or_none()

    async def search_users_by_handle_prefix(
        self, query: str, *, limit: int
    ) -> list[User]:
        me = current_user_id()
        prefix = normalize_handle(query)
        if len(prefix) < 3:
            return []
        stmt = (
            select(User)
            .where(User.handle.is_not(None))
            .where(User.handle.like(f"{prefix}%"))
            .where(User.id != me)
            .order_by(User.handle.asc())
            .limit(limit)
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def is_handle_taken(self, handle: str) -> bool:
        user = await self.get_by_handle(handle)
        return user is not None

    async def get_connection_by_pair(
        self, user_a: uuid.UUID, user_b: uuid.UUID
    ) -> Optional[Connection]:
        low, high = _pair_ids(user_a, user_b)
        # Two-party row: scoped by RLS policies, not owned_by_user().
        stmt = select(Connection).where(Connection.user_low == low, Connection.user_high == high)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_connection_by_id(self, connection_id: uuid.UUID) -> Optional[Connection]:
        me = current_user_id()
        stmt = select(Connection).where(
            Connection.id == connection_id,
            or_(Connection.user_low == me, Connection.user_high == me),
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def list_connections_for_user(self) -> list[tuple[Connection, User]]:
        me = current_user_id()
        stmt = (
            select(Connection, User)
            .join(
                User,
                or_(
                    and_(Connection.user_low == me, User.id == Connection.user_high),
                    and_(Connection.user_high == me, User.id == Connection.user_low),
                ),
            )
            .where(or_(Connection.user_low == me, Connection.user_high == me))
        )
        return list((await self.db.execute(stmt)).all())

    async def add_connection(self, connection: Connection) -> Connection:
        return await self.add_and_flush(connection)

    async def delete_connection(self, connection: Connection) -> None:
        await self.delete(connection)

    async def get_accepted_connection(self, other_user_id: uuid.UUID) -> Optional[Connection]:
        low, high = _pair_ids(current_user_id(), other_user_id)
        stmt = select(Connection).where(
            Connection.user_low == low,
            Connection.user_high == high,
            Connection.status == "accepted",
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()
