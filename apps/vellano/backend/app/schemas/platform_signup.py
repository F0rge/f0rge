from __future__ import annotations

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.platform.service import BLOCKED_EMAIL_TLDS


class SignupCreateRequest(BaseModel):
    legal_name: str = Field(min_length=2, max_length=200)
    trading_name: Optional[str] = Field(default=None, max_length=200)
    slug: str = Field(min_length=3, max_length=32)
    owner_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=12, max_length=200)
    authorised: bool
    privacy_accepted: bool
    privacy_version: str = Field(min_length=1, max_length=64)

    @field_validator("email")
    @classmethod
    def reject_non_routable_tlds(cls, value: EmailStr) -> EmailStr:
        domain = str(value).rsplit("@", 1)[-1].lower()
        tld = domain.rsplit(".", 1)[-1]
        if tld in BLOCKED_EMAIL_TLDS:
            raise ValueError("Enter a deliverable email address")
        return value

    @field_validator("authorised", "privacy_accepted")
    @classmethod
    def must_be_true(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError("Required")
        return value


class SignupCreateResponse(BaseModel):
    signup_id: UUID
    status: str


class SignupVerifyRequest(BaseModel):
    token: str = Field(min_length=8)


class SignupVerifyResponse(BaseModel):
    signup_id: UUID
    status: str


class SignupStatusResponse(BaseModel):
    status: str
    workspace_url: Optional[str] = None
    failure: Optional[str] = None


class SlugAvailabilityResponse(BaseModel):
    available: bool
    reason: Optional[str] = None


class BrandingResponse(BaseModel):
    display_name: str
    slug: str
