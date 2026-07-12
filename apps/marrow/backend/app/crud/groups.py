from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import BaseCRUD
from app.models.group import Group, GroupMember
from app.models.user import User
from f0rge_db.tenant import current_user_id


class GroupCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_group_by_id(self, group_id: uuid.UUID) -> Optional[Group]:
        # Scoped by RLS policies, not owned_by_user().
        stmt = select(Group).where(Group.id == group_id)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_my_membership(self, group_id: uuid.UUID) -> Optional[GroupMember]:
        me = current_user_id()
        stmt = select(GroupMember).where(
            GroupMember.group_id == group_id,
            GroupMember.user_id == me,
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_membership_for_user(
        self, group_id: uuid.UUID, user_id: uuid.UUID
    ) -> Optional[GroupMember]:
        stmt = select(GroupMember).where(
            GroupMember.group_id == group_id,
            GroupMember.user_id == user_id,
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def list_my_groups(self) -> list[tuple[Group, GroupMember, User]]:
        me = current_user_id()
        stmt = (
            select(Group, GroupMember, User)
            .join(GroupMember, GroupMember.group_id == Group.id)
            .join(User, User.id == Group.owner_id)
            .where(GroupMember.user_id == me)
            .order_by(Group.created_at.desc())
        )
        return list((await self.db.execute(stmt)).all())

    async def count_joined_members(self, group_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
        if not group_ids:
            return {}
        stmt = (
            select(GroupMember.group_id, func.count())
            .where(
                GroupMember.group_id.in_(group_ids),
                GroupMember.status == "joined",
            )
            .group_by(GroupMember.group_id)
        )
        rows = (await self.db.execute(stmt)).all()
        return {group_id: count for group_id, count in rows}

    async def list_members_with_users(self, group_id: uuid.UUID) -> list[tuple[GroupMember, User]]:
        stmt = (
            select(GroupMember, User)
            .join(User, User.id == GroupMember.user_id)
            .where(GroupMember.group_id == group_id)
            .order_by(GroupMember.created_at.asc())
        )
        return list((await self.db.execute(stmt)).all())

    async def add_group(self, group: Group) -> Group:
        return await self.add_and_flush(group)

    async def add_member(self, member: GroupMember) -> GroupMember:
        return await self.add_and_flush(member)

    async def delete_member(self, member: GroupMember) -> None:
        await self.delete(member)

    async def delete_group(self, group: Group) -> None:
        await self.delete(group)

    async def flush(self) -> None:
        await self.db.flush()
