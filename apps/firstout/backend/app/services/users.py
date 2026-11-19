from __future__ import annotations

import uuid
from typing import Optional

from fastapi import Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.crud.role import RoleCRUD
from app.crud.user import TeamCRUD, UserCRUD
from app.exceptions import ForbiddenError
from app.models.team import Team
from app.models.membership import Membership
from f0rge_db.organisation import tenant_id_ctx
from app.models.user import User, UserRole
from app.permissions import SLUG_OWNER, role_slug
from app.schemas.user import ProfileUpdate, UserCreate, UserUpdate, UserResponse
from app.schemas.team import TeamBrief
from app.services.auth import hash_password
from app.services.permissions import PermissionService
from app.services.staff_identity import staff_identity_ctx
from app.services.user_default_location import (
    resolve_writable_default_location_id,
)
from f0rge_core.exceptions import ConflictError, NotFoundError, ValidationError
from f0rge_db.crud import unit_of_work


class UserService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = UserCRUD(db)
        self.team_crud = TeamCRUD(db)
        self.role_crud = RoleCRUD(db)

    async def create(self, data: UserCreate) -> User:
        raise ValidationError("Invite staff from Organisation settings to join with Clerk")

    async def list(self) -> list[UserResponse]:
        users = await self.crud.list_all()
        return [await self._response(user) for user in users if user.role != "system"]

    async def get(self, user_id: uuid.UUID) -> UserResponse:
        user = await self.crud.get_by_id(user_id)
        if user is None or user.role == "system":
            raise NotFoundError("User not found")
        return await self._response(user)

    async def _response(self, user: User) -> UserResponse:
        team_id = tenant_id_ctx.get()
        team = await self.team_crud.get_first()
        member = await self.db.scalar(
            select(Membership).where(Membership.user_id == user.id, Membership.team_id == team_id)
        )
        record = UserResponse.model_validate(user)
        if member is not None:
            record = record.model_copy(
                update={
                    "is_disabled": user.is_disabled or member.is_disabled,
                    "can_edit_display_name": member.is_legacy_home or self._is_actor(user.id),
                }
            )
        if member is not None and not member.is_legacy_home:
            record = record.model_copy(
                update={
                    "team_id": team_id,
                    "team": TeamBrief(id=team.id, name=team.name),
                    "role": member.role,
                    "default_location_id": member.default_location_id,
                }
            )
        return record

    async def update(self, user_id: uuid.UUID, data: UserUpdate) -> UserResponse:
        # Serialize role and access changes, then recheck the actor's current authority.
        await self.team_crud.lock_current()
        actor = staff_identity_ctx.get()
        actor_role = (
            await PermissionService(self.db).require_staff_manager_role(actor.user_id)
            if actor is not None
            else None
        )
        user = await self.crud.get_by_id(user_id, refresh=True)
        if user is None or user.role == "system":
            raise NotFoundError("User not found")

        member = await self.db.scalar(
            select(Membership)
            .where(Membership.user_id == user.id, Membership.team_id == tenant_id_ctx.get())
            .execution_options(populate_existing=True)
        )
        if member is None:
            raise NotFoundError("User not found")
        current_role = role_slug(user.role) if member.is_legacy_home else member.role
        await self._check_access_edit(user_id, current_role, data, actor_role)
        if not member.is_legacy_home:
            if "display_name" in data.model_fields_set and not self._is_actor(user.id):
                raise ValidationError("This display name is managed by the staff member")
            if data.display_name is not None:
                user.display_name = data.display_name
            if data.role is not None:
                await self._require_known_role(data.role)
                if await self._is_owner_user(member.role) and not await self._is_owner_user(
                    data.role
                ):
                    await self._reject_last_owner()
                member.role = data.role
            if data.is_disabled is not None:
                if data.is_disabled and await self._is_owner_user(member.role):
                    await self._reject_last_owner()
                member.is_disabled = data.is_disabled
            if "default_location_id" in data.model_fields_set:
                member.default_location_id = await resolve_writable_default_location_id(
                    self.db, data.default_location_id
                )
            async with unit_of_work(self.db):
                pass
            return next(record for record in await self.list() if record.id == user.id)

        if data.display_name is not None:
            user.display_name = data.display_name
        if data.role is not None:
            await self._require_known_role(data.role)
            new_slug = role_slug(data.role)
            if await self._is_owner_user(role_slug(user.role)) and not await self._is_owner_user(
                new_slug
            ):
                await self._reject_last_owner()
            user.role = new_slug
        if data.is_disabled is not None:
            if data.is_disabled and await self._is_owner_user(role_slug(user.role)):
                await self._reject_last_owner()
            # Staff administration belongs to this organisation. The global
            # identity flag remains authoritative for imported/security blocks.
            member.is_disabled = data.is_disabled
        if "default_location_id" in data.model_fields_set:
            user.default_location_id = await resolve_writable_default_location_id(
                self.db,
                data.default_location_id,
            )

        try:
            await self.crud.commit_refresh(user)
        except IntegrityError as exc:
            raise ConflictError("Email already registered") from exc
        reloaded = await self.crud.get_by_id(user.id)
        assert reloaded is not None
        return next(record for record in await self.list() if record.id == user.id)

    def _is_actor(self, user_id: uuid.UUID) -> bool:
        actor = staff_identity_ctx.get()
        return actor is not None and actor.user_id == user_id

    async def _check_access_edit(
        self, user_id: uuid.UUID, role: str, data: UserUpdate, actor_role: Optional[str]
    ) -> None:
        if actor_role is None:
            return
        if self._is_actor(user_id) and (
            data.is_disabled is True or (data.role is not None and role_slug(data.role) != role)
        ):
            raise ConflictError("You cannot change your own role or disable your own access")
        if not await self._is_owner_user(actor_role) and (
            await self._is_owner_user(role)
            or (data.role is not None and await self._is_owner_user(role_slug(data.role)))
        ):
            raise ForbiddenError(
                "Only an owner can change another owner's access or grant ownership"
            )

    async def _require_known_role(self, slug: str) -> None:
        role = await self.role_crud.get_by_slug(role_slug(slug))
        if role is None:
            raise ValidationError("Unknown role")

    async def _is_owner_user(self, slug: str) -> bool:
        return slug == SLUG_OWNER or slug in await self.role_crud.list_owner_slugs()

    async def _reject_last_owner(self) -> None:
        slugs = await self.role_crud.list_owner_slugs()
        if await self.role_crud.count_users_with_slugs(slugs, active_only=True) <= 1:
            raise ConflictError("Cannot demote the last owner")


class ProfileService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = UserCRUD(db)

    async def update(
        self,
        user_id: uuid.UUID,
        data: ProfileUpdate,
        response: Response,
    ) -> User:
        user = await self.crud.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found")

        if data.display_name is not None:
            user.display_name = data.display_name
        if "default_location_id" in data.model_fields_set:
            location_id = await resolve_writable_default_location_id(
                self.db, data.default_location_id
            )
            member = await self.db.scalar(
                select(Membership).where(
                    Membership.user_id == user.id, Membership.team_id == tenant_id_ctx.get()
                )
            )
            if member is None:
                raise NotFoundError("Membership not found")
            if not member.is_legacy_home:
                member.default_location_id = location_id
            else:
                user.default_location_id = location_id

        try:
            await self.crud.commit_refresh(user)
        except IntegrityError as exc:
            raise ConflictError("Email already registered") from exc
        reloaded = await self.crud.get_by_id(user.id)
        assert reloaded is not None
        return reloaded


class BootstrapService:
    DEFAULT_TEAM_NAME = "Firstout"

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def seed_if_empty(self) -> None:
        if await self.db.scalar(select(User.id).limit(1)) is not None:
            return

        async with unit_of_work(self.db):
            team: Optional[Team] = await self.db.scalar(select(Team).limit(1))
            if team is None:
                team = Team(name=self.DEFAULT_TEAM_NAME)
                self.db.add(team)
                await self.db.flush()

            owner = User(
                team_id=team.id,
                email=settings.seed_owner_email,
                password_hash=hash_password(settings.seed_owner_password),
                display_name="Owner",
                role=UserRole.OWNER,
            )
            self.db.add(owner)
            await self.db.flush()
            self.db.add(
                Membership(
                    user_id=owner.id,
                    team_id=team.id,
                    role=owner.role,
                    permission_source="legacy",
                    is_legacy_home=True,
                    is_disabled=False,
                )
            )
