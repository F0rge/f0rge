from __future__ import annotations

import uuid

from typing import Optional

from pydantic import BaseModel, EmailStr, Field

from app.schemas.team import TeamBrief


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    email: EmailStr


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirmRequest(BaseModel):
    token: str = Field(min_length=1)
    password: str = Field(min_length=8)
    password_confirm: str = Field(min_length=8)


class PasswordResetMessage(BaseModel):
    message: str


class MeResponse(BaseModel):
    id: uuid.UUID
    email: EmailStr
    display_name: Optional[str]
    role: str
    permissions: list[str]
    team: TeamBrief
    default_location_id: Optional[uuid.UUID] = None
