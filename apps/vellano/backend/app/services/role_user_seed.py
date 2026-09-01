from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.crud.user import TeamCRUD, UserCRUD
from app.models.user import User, UserRole
from app.services.auth import hash_password
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

        async with unit_of_work(self.db):
            for email, role, password_setting in ROLE_USER_SPECS:
                if await self.user_crud.get_by_email(email) is not None:
                    continue
                password = getattr(settings, password_setting)
                user = User(
                    team_id=team.id,
                    email=email,
                    password_hash=hash_password(password),
                    display_name=role.value.title(),
                    role=role,
                )
                await self.user_crud.add_and_flush(user)
