from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.crud.user import TeamCRUD, UserCRUD
from app.models.user import User, UserRole
from app.services.auth import hash_password
from app.services.user_default_location import bedfordview_default_location_id
from f0rge_db.crud import unit_of_work

ROLE_USER_SPECS: tuple[tuple[str, UserRole, str], ...] = (
    ("till@example.com", UserRole.TILL, "seed_till_password"),
    ("books@example.com", UserRole.BOOKS, "seed_books_password"),
    ("warehouse@example.com", UserRole.WAREHOUSE, "seed_warehouse_password"),
    ("buyer@example.com", UserRole.BUYER, "seed_buyer_password"),
)


class RoleUserSeedService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.user_crud = UserCRUD(db)
        self.team_crud = TeamCRUD(db)

    async def seed(self) -> None:
        team = await self.team_crud.get_first()
        if team is None:
            return

        bedfordview_id = await bedfordview_default_location_id(self.db)

        async with unit_of_work(self.db):
            for email, role, password_setting in ROLE_USER_SPECS:
                if await self.user_crud.get_by_email(email) is not None:
                    continue
                password = getattr(settings, password_setting)
                default_location_id = bedfordview_id if role == UserRole.TILL else None
                user = User(
                    team_id=team.id,
                    email=email,
                    password_hash=hash_password(password),
                    display_name=role.value.title(),
                    role=role,
                    default_location_id=default_location_id,
                )
                await self.user_crud.add_and_flush(user)

            if bedfordview_id is not None:
                for user in await self.user_crud.list_till_with_null_default():
                    user.default_location_id = bedfordview_id
