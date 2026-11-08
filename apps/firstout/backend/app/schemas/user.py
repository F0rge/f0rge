from __future__ import annotations

import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.schemas.team import TeamBrief


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    role: str = Field(min_length=1, max_length=32)
    display_name: Optional[str] = None
    default_location_id: Optional[uuid.UUID] = None


class UserUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    display_name: Optional[str] = None
    role: Optional[str] = Field(default=None, min_length=1, max_length=32)
    is_disabled: Optional[bool] = None
    default_location_id: Optional[uuid.UUID] = None


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    display_name: Optional[str] = None
    default_location_id: Optional[uuid.UUID] = None


class UserResponse(BaseModel):
    id: uuid.UUID
    email: EmailStr
    display_name: Optional[str]
    role: str
    is_disabled: bool
    team_id: uuid.UUID
    team: TeamBrief
    default_location_id: Optional[uuid.UUID] = None

    model_config = ConfigDict(from_attributes=True)
