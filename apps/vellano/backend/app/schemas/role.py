from __future__ import annotations

import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class RoleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    permissions: list[str] = Field(default_factory=list)


class RoleUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    permissions: Optional[list[str]] = None


class RoleResponse(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    is_system: bool
    is_owner_preset: bool
    permissions: list[str]

    model_config = ConfigDict(from_attributes=True)
