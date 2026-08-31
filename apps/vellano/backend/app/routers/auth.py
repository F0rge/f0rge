from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Response, status

from app.dependencies.auth import get_auth_service, get_current_user_id
from app.schemas.auth import LoginRequest, LoginResponse, MeResponse
from app.services.auth import AuthService

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


@router.get("/me", response_model=MeResponse)
async def me(
    user_id: uuid.UUID = Depends(get_current_user_id),
    service: AuthService = Depends(get_auth_service),
):
    return await service.get_me(user_id)
