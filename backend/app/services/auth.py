from __future__ import annotations

import datetime
import uuid
from typing import Optional

import bcrypt
import jwt
from fastapi import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.exceptions import ConflictError, UnauthorizedError, ValidationError
from app.models.user import User

JWT_ALGORITHM = "HS256"
JWT_COOKIE_NAME = "ht_session"
JWT_TTL_DAYS = 90
MIN_PASSWORD_LENGTH = 8


def _require_jwt_secret() -> str:
    if not settings.jwt_secret:
        raise ValidationError("JWT secret not configured")
    return settings.jwt_secret


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(password: str, password_hash: str) -> bool:
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


def _validate_password(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValidationError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters")


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> Optional[User]:
    return (
        await db.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()


async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    return (
        await db.execute(select(User).where(User.email == email))
    ).scalar_one_or_none()


async def signup(
    db: AsyncSession,
    email: str,
    password: str,
    response: Response,
) -> dict[str, object]:
    _validate_password(password)

    existing = await get_user_by_email(db, email)
    if existing is not None:
        raise ConflictError("Email already registered")

    user = User(email=email, password_hash=_hash_password(password))
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(user.id)
    set_session_cookie(response, token)
    return {"authenticated": True, "user_id": str(user.id), "email": user.email}


async def login(
    db: AsyncSession,
    email: str,
    password: str,
    response: Response,
) -> dict[str, object]:
    user = await get_user_by_email(db, email)
    if user is None or not _verify_password(password, user.password_hash):
        raise UnauthorizedError("Invalid email or password")

    token = create_access_token(user.id)
    set_session_cookie(response, token)
    return {"authenticated": True, "user_id": str(user.id), "email": user.email}


async def logout(response: Response) -> dict[str, bool]:
    clear_session_cookie(response)
    return {"authenticated": False}


async def get_me(db: AsyncSession, user_id: uuid.UUID) -> dict[str, object]:
    user = await get_user_by_id(db, user_id)
    if user is None:
        raise UnauthorizedError("Invalid session")
    return {"authenticated": True, "user_id": str(user.id), "email": user.email}


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def signup(
        self,
        email: str,
        password: str,
        response: Response,
    ) -> dict[str, object]:
        return await signup(self.db, email, password, response)

    async def login(
        self,
        email: str,
        password: str,
        response: Response,
    ) -> dict[str, object]:
        return await login(self.db, email, password, response)

    async def logout(self, response: Response) -> dict[str, bool]:
        return await logout(response)

    async def get_me(self, user_id: uuid.UUID) -> dict[str, object]:
        return await get_me(self.db, user_id)
