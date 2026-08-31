from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.crud.user import TeamCRUD, UserCRUD
from app.models.team import Team
from app.models.user import User, UserRole
from app.schemas.user import ProfileUpdate, UserCreate, UserUpdate
from app.services.auth import hash_password, validate_password
from f0rge_core.exceptions import ConflictError, NotFoundError, ValidationError
from f0rge_db.crud import unit_of_work


class UserService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = UserCRUD(db)
        self.team_crud = TeamCRUD(db)

    async def create(self, data: UserCreate) -> User:
        validate_password(data.password)
        team = await self.team_crud.get_first()
        if team is None:
            raise ValidationError("Team not configured")

        user = User(
            team_id=team.id,
            email=data.email,
            password_hash=hash_password(data.password),
            display_name=data.display_name,
            role=data.role,
        )
        await self.crud.add_and_flush(user)
        try:
            await self.crud.commit_refresh(user)
        except IntegrityError as exc:
            raise ConflictError("Email already registered") from exc
        reloaded = await self.crud.get_by_id(user.id)
        assert reloaded is not None
        return reloaded

    async def list(self) -> list[User]:
        return await self.crud.list_all()

    async def update(self, user_id: uuid.UUID, data: UserUpdate) -> User:
        user = await self.crud.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found")

        if data.email is not None:
            user.email = data.email
        if data.display_name is not None:
            user.display_name = data.display_name
        if data.role is not None:
            user.role = data.role
        if data.is_disabled is not None:
            user.is_disabled = data.is_disabled
        if data.password is not None:
            validate_password(data.password)
            user.password_hash = hash_password(data.password)

        try:
            await self.crud.commit_refresh(user)
        except IntegrityError as exc:
            raise ConflictError("Email already registered") from exc
        reloaded = await self.crud.get_by_id(user.id)
        assert reloaded is not None
        return reloaded


class ProfileService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = UserCRUD(db)

    async def update(self, user_id: uuid.UUID, data: ProfileUpdate) -> User:
        user = await self.crud.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found")

        if data.email is not None:
            user.email = data.email
        if data.display_name is not None:
            user.display_name = data.display_name
        if data.password is not None:
            validate_password(data.password)
            user.password_hash = hash_password(data.password)

        try:
            await self.crud.commit_refresh(user)
        except IntegrityError as exc:
            raise ConflictError("Email already registered") from exc
        reloaded = await self.crud.get_by_id(user.id)
        assert reloaded is not None
        return reloaded


class BootstrapService:
    DEFAULT_TEAM_NAME = "Vellano"

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.user_crud = UserCRUD(db)
        self.team_crud = TeamCRUD(db)

    async def seed_if_empty(self) -> None:
        if await self.user_crud.count() > 0:
            return

        async with unit_of_work(self.db):
            team: Optional[Team] = await self.team_crud.get_first()
            if team is None:
                team = Team(name=self.DEFAULT_TEAM_NAME)
                await self.team_crud.add_and_flush(team)

            owner = User(
                team_id=team.id,
                email=settings.seed_owner_email,
                password_hash=hash_password(settings.seed_owner_password),
                display_name="Owner",
                role=UserRole.OWNER,
            )
            await self.user_crud.add_and_flush(owner)
