from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response, status

from app.dependencies.auth import (
    get_auth_service,
    get_current_user_id,
    get_password_reset_service,
)
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    MeResponse,
    PasswordResetConfirmRequest,
    PasswordResetMessage,
    PasswordResetRequest,
)
from app.services.auth import AuthService
from app.services.password_reset import PasswordResetService

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    response: Response,
    service: AuthService = Depends(get_auth_service),
):
    return await service.login(body.email, body.password, response)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    service: AuthService = Depends(get_auth_service),
):
    await service.logout(response)


@router.post("/forgot-password", response_model=PasswordResetMessage)
async def forgot_password(
    body: PasswordResetRequest,
    request: Request,
    background: BackgroundTasks,
    service: PasswordResetService = Depends(get_password_reset_service),
):
    return await service.request_reset(body.email, request, background)


@router.post("/reset-password", response_model=PasswordResetMessage)
async def reset_password(
    body: PasswordResetConfirmRequest,
    request: Request,
    service: PasswordResetService = Depends(get_password_reset_service),
):
    return await service.confirm_reset(body, request)


@router.get("/me", response_model=MeResponse)
async def me(
    user_id: uuid.UUID = Depends(get_current_user_id),
    service: AuthService = Depends(get_auth_service),
):
    return await service.get_me(user_id)
