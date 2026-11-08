from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.services.tenant_host import RESERVED_SLUGS, SLUG_PATTERN


class SignupIntent(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=63)
    legal_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    address: str = Field(default="", max_length=2000)
    vat_number: str = Field(default="", max_length=64)
    location_name: str = Field(default="Main location", min_length=1, max_length=255)

    @field_validator("slug")
    @classmethod
    def valid_slug(cls, value: str) -> str:
        if not SLUG_PATTERN.fullmatch(value) or value in RESERVED_SLUGS:
            raise ValueError("Use a non-reserved lowercase business URL")
        return value


class OrganisationInvitationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    role: str = Field(min_length=1, max_length=32)
