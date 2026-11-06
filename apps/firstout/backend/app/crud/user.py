from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import defer, selectinload

from app.models.membership import Membership
from app.models.team import Team
from app.models.user import User, UserRole
from f0rge_core.exceptions import UnauthorizedError
from f0rge_db.crud import BaseCRUD
from f0rge_db.organisation import tenant_id_ctx


def require_directory_tenant() -> uuid.UUID:
    tenant_id = tenant_id_ctx.get()
    if tenant_id is None:
        raise UnauthorizedError("Tenant context required for directory access")
    return tenant_id


class IdentityLookup:
    """Exact-key pre-authentication lookups; never enumerate or auto-link identities.

    Passwords are loaded only for the legacy password verifier. Callers must
    verify credentials and resolve membership before establishing tenant scope.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def by_session_subject(self, user_id: uuid.UUID) -> Optional[User]:
        return await self.db.scalar(
            select(User)
            .options(defer(User.password_hash, raiseload=True))
            .where(User.id == user_id)
        )

    async def by_clerk_subject(self, subject: str) -> Optional[User]:
        return await self.db.scalar(
            select(User)
            .options(defer(User.password_hash, raiseload=True))
            .where(User.clerk_user_id == subject)
        )

    async def for_password_login(self, email: str) -> Optional[User]:
        return await self.db.scalar(select(User).where(User.email == email))

    async def for_password_reset(self, email: str) -> Optional[User]:
        return await self.db.scalar(
            select(User)
            .options(defer(User.password_hash, raiseload=True))
            .where(User.email == email)
        )


class ScopedDirectoryCRUD(BaseCRUD):
    """Directory writes require scope and matching home ownership.

    A person may edit their own global profile while in another membership;
    another tenant's administrator cannot mutate that global identity.
    """

    def _check_object(self, obj):
        from app.models.password_reset_token import PasswordResetToken
        from f0rge_db.auth_context import user_id_ctx

        tenant_id = require_directory_tenant()
        if isinstance(obj, Team):
            allowed = obj.id == tenant_id
        elif isinstance(obj, User):
            allowed = obj.team_id == tenant_id or obj.id == user_id_ctx.get()
        elif isinstance(obj, Membership):
            allowed = obj.team_id == tenant_id
        elif isinstance(obj, PasswordResetToken):
            # Token owner is checked by the async write path below.
            return
        else:
            allowed = False
        if not allowed:
            raise UnauthorizedError("Directory object is outside tenant scope")

    async def _check_write(self, obj):
        from app.models.password_reset_token import PasswordResetToken

        self._check_object(obj)
        if isinstance(obj, PasswordResetToken):
            user = await UserCRUD(self.db).get_by_id(obj.user_id)
            if user is None:
                raise UnauthorizedError("Reset owner is outside tenant scope")

    def add(self, obj):
        from app.models.password_reset_token import PasswordResetToken

        self._check_object(obj)
        if isinstance(obj, PasswordResetToken):
            raise UnauthorizedError("Use scoped async reset token insertion")
        super().add(obj)

    async def add_and_flush(self, obj):
        await self._check_write(obj)
        return await super().add_and_flush(obj)

    async def delete(self, obj):
        await self._check_write(obj)
        await super().delete(obj)

    async def delete_and_commit(self, obj):
        await self._check_write(obj)
        await super().delete_and_commit(obj)

    async def save(self):
        require_directory_tenant()
        for obj in list(self.db.new) + list(self.db.dirty) + list(self.db.deleted):
            if isinstance(obj, (User, Team, Membership)):
                await self._check_write(obj)
        await super().save()

    async def commit_refresh(self, obj):
        await self._check_write(obj)
        return await super().commit_refresh(obj)

    async def refresh(self, obj):
        await self._check_write(obj)
        await super().refresh(obj)

    async def flush(self):
        require_directory_tenant()
        for obj in list(self.db.new) + list(self.db.dirty) + list(self.db.deleted):
            if isinstance(obj, (User, Team, Membership)):
                await self._check_write(obj)
        await super().flush()


class TeamCRUD(ScopedDirectoryCRUD):
    async def get_by_id(self, team_id: uuid.UUID) -> Optional[Team]:
        tenant_id = require_directory_tenant()
        return await self.db.scalar(select(Team).where(Team.id == team_id, Team.id == tenant_id))

    async def get_first(self) -> Optional[Team]:
        return await self.get_by_id(require_directory_tenant())

    async def count(self) -> int:
        return int(
            await self.db.scalar(
                select(func.count()).select_from(Team).where(Team.id == require_directory_tenant())
            )
        )


class UserCRUD(ScopedDirectoryCRUD):
    def _query(self):
        return (
            select(User)
            .options(selectinload(User.team), defer(User.password_hash, raiseload=True))
            .join(Membership, Membership.user_id == User.id)
            .where(Membership.team_id == require_directory_tenant())
        )

    async def get_by_id(self, user_id: uuid.UUID) -> Optional[User]:
        return await self.db.scalar(self._query().where(User.id == user_id))

    async def get_by_email(self, email: str) -> Optional[User]:
        return await self.db.scalar(self._query().where(User.email == email))

    async def count(self) -> int:
        return int(await self.db.scalar(select(func.count()).select_from(self._query().subquery())))

    async def list_all(self) -> list[User]:
        return list((await self.db.scalars(self._query().order_by(User.email))).all())

    async def list_till_with_null_default(self) -> list[User]:
        return list(
            (
                await self.db.scalars(
                    self._query().where(
                        User.role == UserRole.TILL,
                        User.default_location_id.is_(None),
                        User.team_id == require_directory_tenant(),
                    )
                )
            ).all()
        )
