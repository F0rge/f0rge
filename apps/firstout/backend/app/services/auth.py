from __future__ import annotations

from typing import Optional

import uuid

import bcrypt
from fastapi import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.crud.user import UserCRUD
from app.permissions import role_slug
from app.services.staff_identity import staff_identity_ctx
from fastapi import Request
from app.services.permissions import PermissionService
from f0rge_core.exceptions import UnauthorizedError, ValidationError

JWT_COOKIE_NAME = "firstout_session"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        # Clerk-only identities deliberately have no local password verifier.
        return False


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=JWT_COOKIE_NAME,
        path="/",
        secure=settings.cookie_secure,
    )


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = UserCRUD(db)

    async def login(
        self, email: str, password: str, response: Response, request: Optional[Request] = None
    ) -> dict[str, str]:
        raise ValidationError("Sign in with Clerk; local password login has been retired")

    async def logout(self, response: Response) -> None:
        clear_session_cookie(response)

    async def get_me(self, user_id: uuid.UUID) -> dict[str, object]:
        user = await self.crud.get_by_id(user_id)
        if user is None or user.is_disabled:
            raise UnauthorizedError("Invalid session")
        identity = staff_identity_ctx.get()
        return {
            "id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "role": identity.role if identity else role_slug(user.role),
            "permissions": await PermissionService(self.db).keys_for_user(user.id),
            "team": {"id": identity.team_id, "name": identity.team_name}
            if identity
            else {"id": user.team.id, "name": user.team.name},
            "default_location_id": identity.default_location_id
            if identity
            else user.default_location_id,
        }
