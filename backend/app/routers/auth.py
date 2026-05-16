from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_session
from app.models.session import AuthSession
from app.schemas.auth import AuthStatus, PinLogin
from app.services import auth as auth_service

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login")
async def login(body: PinLogin, response: Response, db: AsyncSession = Depends(get_db)):
    return await auth_service.login(db, body.pin, response)


@router.post("/logout")
async def logout(
    response: Response,
    session: AuthSession = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
):
    return await auth_service.logout(db, session, response)


@router.get("/me", response_model=AuthStatus)
async def me(session: AuthSession = Depends(get_current_session)):
    return AuthStatus(authenticated=True)
