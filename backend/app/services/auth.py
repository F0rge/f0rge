from __future__ import annotations

import datetime
import secrets

import bcrypt
from fastapi import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.exceptions import UnauthorizedError, ValidationError
from app.models.session import AuthSession


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
