from __future__ import annotations

import datetime
import secrets
from typing import Optional

import bcrypt
from fastapi import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.exceptions import UnauthorizedError, ValidationError
from app.models.session import AuthSession


async def get_session_by_token(db: AsyncSession, token: Optional[str]) -> Optional[AuthSession]:
    """Look up a session row by token. Returns None if token is falsy or not found.

    Does NOT check expiry — caller is responsible for that check.
    """
    if not token:
        return None
    return (
        await db.execute(select(AuthSession).where(AuthSession.token == token))
    ).scalar_one_or_none()


async def login(
    db: AsyncSession,
    pin: str,
    response: Response,
) -> dict[str, bool]:
    if not settings.pin_hash:
        raise ValidationError("PIN not configured")

    if not bcrypt.checkpw(pin.encode("utf-8"), settings.pin_hash.encode("utf-8")):
        raise UnauthorizedError("Invalid PIN")

    token = secrets.token_hex(32)
    now = datetime.datetime.utcnow()
    expires = now + datetime.timedelta(days=90)

    session = AuthSession(token=token, created_at=now, expires_at=expires)
    db.add(session)
    await db.commit()

    response.set_cookie(
        key="ht_session",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=90 * 24 * 60 * 60,
    )
    return {"authenticated": True}


async def logout(
    db: AsyncSession,
    session: AuthSession,
    response: Response,
) -> dict[str, bool]:
    await db.delete(session)
    await db.commit()
    response.delete_cookie(key="ht_session")
    return {"authenticated": False}


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def login(self, pin: str, response: Response) -> dict[str, bool]:
        return await login(self.db, pin, response)

    async def logout(self, session: AuthSession, response: Response) -> dict[str, bool]:
        return await logout(self.db, session, response)
