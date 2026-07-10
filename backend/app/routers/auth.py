from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Response

from app.dependencies.auth import get_auth_service
from app.middleware.auth import get_current_user_id
from app.schemas.auth import AuthStatus, LoginRequest, SignupRequest
from app.services.auth import AuthService

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/signup", response_model=AuthStatus)
async def signup(
    body: SignupRequest,
    response: Response,
    service: AuthService = Depends(get_auth_service),
):
    return await service.signup(body.email, body.password, response)


@router.post("/login", response_model=AuthStatus)
async def login(
    body: LoginRequest,
    response: Response,
    service: AuthService = Depends(get_auth_service),
):
    return await service.login(body.email, body.password, response)


@router.post("/logout", response_model=AuthStatus)
async def logout(
    response: Response,
    service: AuthService = Depends(get_auth_service),
):
    return await service.logout(response)


@router.get("/me", response_model=AuthStatus)
async def me(
    user_id: uuid.UUID = Depends(get_current_user_id),
    service: AuthService = Depends(get_auth_service),
):
    return await service.get_me(user_id)
