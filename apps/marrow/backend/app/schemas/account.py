from __future__ import annotations

import datetime
from typing import Optional

from pydantic import BaseModel, Field


class AccountResponse(BaseModel):
    user_id: str
    email: str
    display_name: Optional[str] = None
    handle: Optional[str] = None
    avatar_default_index: int
    has_custom_avatar: bool
    created_at: datetime.datetime


class AccountUpdate(BaseModel):
    display_name: Optional[str] = Field(default=None, max_length=100)
    handle: Optional[str] = Field(default=None, min_length=3, max_length=30)


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


class AccountDeleteRequest(BaseModel):
    password: str
