from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import case, select
from f0rge_db.organisation import tenant_id_ctx
from app.models.membership import Membership
from app.models.team import Team
from app.models.user import User

from app.services.staff_identity import staff_identity_ctx
from app.crud.role import RoleCRUD
from app.crud.user import UserCRUD, require_directory_tenant
from app.exceptions import ForbiddenError
from app.permissions import PERMISSION_CATALOG, SLUG_OWNER, USERS_MANAGE, role_slug


class PermissionService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.user_crud = UserCRUD(db)
        self.role_crud = RoleCRUD(db)

    async def keys_for_user(self, user_id: uuid.UUID) -> list[str]:
        return sorted(await self._key_set(user_id))

    async def has_permission(self, user_id: uuid.UUID, key: str) -> bool:
        return key in await self._key_set(user_id)

    async def has_any(self, user_id: uuid.UUID, keys: tuple[str, ...]) -> bool:
        granted = await self._key_set(user_id)
        return any(key in granted for key in keys)

    async def require_staff_manager_role(self, user_id: uuid.UUID) -> str:
        """Recheck current staff authority under the caller's Team row lock."""
        team_id = require_directory_tenant()
        # Project fresh column values because the request dependencies already loaded
        # the ORM identity and membership, potentially before a concurrent demotion.
        slug = await self.db.scalar(
            select(case((Membership.is_legacy_home, User.role), else_=Membership.role))
            .select_from(Membership)
            .join(User, User.id == Membership.user_id)
            .join(Team, Team.id == Membership.team_id)
            .where(
                Membership.team_id == team_id,
                Membership.user_id == user_id,
                Membership.is_disabled.is_(False),
                User.is_disabled.is_(False),
                User.role != "system",
                Team.status == "active",
            )
        )
        if slug is None or USERS_MANAGE not in await self._role_keys(slug, refresh=True):
            raise ForbiddenError("Staff management permission is required")
        return slug

    async def _key_set(self, user_id: uuid.UUID) -> frozenset[str]:
        user = await self.user_crud.get_by_id(user_id)
        if user is None or user.is_disabled:
            return frozenset()
        identity = staff_identity_ctx.get()
        slug = identity.role if identity and identity.user_id == user_id else role_slug(user.role)
        team_id = tenant_id_ctx.get()
        if team_id is not None:
            member = await self.db.scalar(
                select(Membership).where(
                    Membership.user_id == user_id, Membership.team_id == team_id
                )
            )
            if member is None or member.is_disabled:
                return frozenset()
            slug = role_slug(user.role) if member.is_legacy_home else member.role
        return await self._role_keys(slug)

    async def _role_keys(self, slug: str, *, refresh: bool = False) -> frozenset[str]:
        role = await self.role_crud.get_by_slug(slug, refresh=refresh)
        if slug == SLUG_OWNER or (role is not None and role.is_owner_preset):
            return frozenset(PERMISSION_CATALOG)
        if role is None:
            return frozenset()
        return frozenset(permission.key for permission in role.permissions)
