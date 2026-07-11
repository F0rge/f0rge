from __future__ import annotations

import datetime
import uuid

import bcrypt
import jwt
from fastapi import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.crud.auth import UserCRUD
from app.exceptions import ConflictError, UnauthorizedError, ValidationError
from app.models.user import User
from app.services.avatar_defaults import default_avatar_index
from app.services.user_provisioning import provision_user_catalogs, repair_infrastructure_catalogs

JWT_ALGORITHM = "HS256"
JWT_COOKIE_NAME = "ht_session"
JWT_TTL_DAYS = 90
MIN_PASSWORD_LENGTH = 8


def _require_jwt_secret() -> str:
    if not settings.jwt_secret:
        raise ValidationError("JWT secret not configured")
    return settings.jwt_secret


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_access_token(user_id: uuid.UUID) -> str:
    now = datetime.datetime.utcnow()
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + datetime.timedelta(days=JWT_TTL_DAYS),
    }
    return jwt.encode(payload, _require_jwt_secret(), algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> uuid.UUID:
    try:
        payload = jwt.decode(token, _require_jwt_secret(), algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError as exc:
        raise UnauthorizedError("Invalid session") from exc

    sub = payload.get("sub")
    if not sub:
        raise UnauthorizedError("Invalid session")

    try:
        return uuid.UUID(str(sub))
    except ValueError as exc:
        raise UnauthorizedError("Invalid session") from exc


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=JWT_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=JWT_TTL_DAYS * 24 * 60 * 60,
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=JWT_COOKIE_NAME)


def validate_password(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValidationError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters")


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = UserCRUD(db)

    async def signup(
        self,
        email: str,
        password: str,
        response: Response,
    ) -> dict[str, object]:
        validate_password(password)

        existing = await self.crud.get_by_email(email)
        if existing is not None:
            raise ConflictError("Email already registered")

        user = User(email=email, password_hash=hash_password(password))
        await self.crud.add_and_flush(user)
        user.avatar_default_index = default_avatar_index(user.id)
        await provision_user_catalogs(self.db, user.id)
        await self.crud.commit_refresh(user)

        token = create_access_token(user.id)
        set_session_cookie(response, token)
        return {"authenticated": True, "user_id": str(user.id), "email": user.email}

    async def login(
        self,
        email: str,
        password: str,
        response: Response,
    ) -> dict[str, object]:
        user = await self.crud.get_by_email(email)
        if user is None or not verify_password(password, user.password_hash):
            raise UnauthorizedError("Invalid email or password")

        await repair_infrastructure_catalogs(self.db, user.id)
        await self.crud.commit_refresh(user)

        token = create_access_token(user.id)
        set_session_cookie(response, token)
        return {"authenticated": True, "user_id": str(user.id), "email": user.email}

    async def logout(self, response: Response) -> dict[str, bool]:
        clear_session_cookie(response)
        return {"authenticated": False}

    async def get_me(self, user_id: uuid.UUID) -> dict[str, object]:
        user = await self.crud.get_by_id(user_id)
        if user is None:
            raise UnauthorizedError("Invalid session")
        return {"authenticated": True, "user_id": str(user.id), "email": user.email}
