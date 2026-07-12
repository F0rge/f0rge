from __future__ import annotations

import re
import uuid
import datetime

from pydantic import BaseModel, Field, field_validator

from f0rge_core.exceptions import ValidationError

HANDLE_PATTERN = re.compile(r"^[a-z0-9_]{3,30}$")


def normalize_handle(value: str) -> str:
    return value.strip().lower().lstrip("@")


def validate_handle_format(value: str) -> str:
    normalized = normalize_handle(value)
    if not HANDLE_PATTERN.match(normalized):
        raise ValidationError("Handle must be 3-30 characters: a-z, 0-9, _")
    return normalized


class PublicUserCard(BaseModel):
    handle: str
    display_name: str | None = None
    avatar_default_index: int


class HandleAvailableResponse(BaseModel):
    available: bool


class ConnectionRequest(BaseModel):
    handle: str = Field(min_length=3, max_length=30)


class ConnectionItem(BaseModel):
    id: uuid.UUID
    user: PublicUserCard
    since: datetime.datetime | None = None
    created_at: datetime.datetime | None = None


class ConnectionListResponse(BaseModel):
    accepted: list[ConnectionItem]
    pending_incoming: list[ConnectionItem]
    pending_outgoing: list[ConnectionItem]


class HandleField(BaseModel):
    handle: str = Field(min_length=3, max_length=30)

    @field_validator("handle")
    @classmethod
    def check_handle(cls, value: str) -> str:
        return validate_handle_format(value)


class GroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=60)


class GroupRename(BaseModel):
    name: str = Field(min_length=1, max_length=60)


class GroupInviteRequest(HandleField):
    pass


class GroupListItem(BaseModel):
    id: uuid.UUID
    name: str
    owner: PublicUserCard
    member_count: int
    my_status: str
    my_role: str


class GroupListResponse(BaseModel):
    groups: list[GroupListItem]


class GroupMemberItem(BaseModel):
    handle: str
    display_name: str | None = None
    avatar_default_index: int
    role: str
    status: str
    joined_at: datetime.datetime | None = None


class GroupDetailResponse(BaseModel):
    id: uuid.UUID
    name: str
    owner: PublicUserCard
    member_count: int
    my_status: str
    my_role: str
    members: list[GroupMemberItem]
