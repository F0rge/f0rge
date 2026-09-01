from __future__ import annotations

import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import UserRole
from app.schemas.team import TeamBrief


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    role: UserRole
    display_name: Optional[str] = None
    default_location_id: Optional[uuid.UUID] = None


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    display_name: Optional[str] = None
    role: Optional[UserRole] = None
    is_disabled: Optional[bool] = None
    password: Optional[str] = Field(default=None, min_length=8)
    default_location_id: Optional[uuid.UUID] = None


class ProfileUpdate(BaseModel):
    email: Optional[EmailStr] = None
    display_name: Optional[str] = None
    password: Optional[str] = Field(default=None, min_length=8)
    default_location_id: Optional[uuid.UUID] = None


class UserResponse(BaseModel):
    id: uuid.UUID
    email: EmailStr
    display_name: Optional[str]
    role: UserRole
    is_disabled: bool
    team_id: uuid.UUID
    team: TeamBrief
    default_location_id: Optional[uuid.UUID] = None

    model_config = ConfigDict(from_attributes=True)
