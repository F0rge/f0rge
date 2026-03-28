from __future__ import annotations

import datetime
import secrets

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.middleware.auth import get_current_session
from app.models.session import AuthSession
from app.schemas.auth import AuthStatus, PinLogin

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login")
def login(body: PinLogin, response: Response, db: Session = Depends(get_db)):
    if not settings.pin_hash:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="PIN not configured",
        )

    if not bcrypt.checkpw(
        body.pin.encode("utf-8"), settings.pin_hash.encode("utf-8")
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid PIN",
        )

    token = secrets.token_hex(32)
    now = datetime.datetime.utcnow()
    expires = now + datetime.timedelta(days=90)

    session = AuthSession(token=token, created_at=now, expires_at=expires)
    db.add(session)
    db.commit()

    response.set_cookie(
        key="ht_session",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=90 * 24 * 60 * 60,
    )
    return {"authenticated": True}


@router.post("/logout")
def logout(
    response: Response,
    session: AuthSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    db.delete(session)
    db.commit()
    response.delete_cookie(key="ht_session")
    return {"authenticated": False}


@router.get("/me", response_model=AuthStatus)
def me(session: AuthSession = Depends(get_current_session)):
    return AuthStatus(authenticated=True)
