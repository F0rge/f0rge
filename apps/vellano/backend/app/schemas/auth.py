from __future__ import annotations

import uuid

from typing import Optional

from pydantic import BaseModel, EmailStr

from app.schemas.team import TeamBrief


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    email: EmailStr


class MeResponse(BaseModel):
    id: uuid.UUID
    email: EmailStr
    display_name: Optional[str]
    role: str
    team: TeamBrief
    default_location_id: Optional[uuid.UUID] = None
