from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from app.dependencies.auth import get_auth_service
from app.middleware.auth import get_current_session
from app.models.session import AuthSession
from app.schemas.auth import AuthStatus, PinLogin
from app.services.auth import AuthService

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login", response_model=AuthStatus)
async def login(
    body: PinLogin,
    response: Response,
    service: AuthService = Depends(get_auth_service),
):
    return await service.login(body.pin, response)


@router.post("/logout", response_model=AuthStatus)
async def logout(
    response: Response,
    session: AuthSession = Depends(get_current_session),
    service: AuthService = Depends(get_auth_service),
):
    return await service.logout(session, response)


@router.get("/me", response_model=AuthStatus)
async def me(session: AuthSession = Depends(get_current_session)):
    return AuthStatus(authenticated=True)
