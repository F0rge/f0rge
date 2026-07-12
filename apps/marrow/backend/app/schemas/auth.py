from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field

from app.schemas.social import HandleField


class SignupRequest(HandleField):
    email: EmailStr
    password: str = Field(min_length=8)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthStatus(BaseModel):
    authenticated: bool
    user_id: str | None = None
    email: str | None = None
    handle: str | None = None
