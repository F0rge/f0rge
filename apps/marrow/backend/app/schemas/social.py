from __future__ import annotations

import re
import uuid
import datetime

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

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


class UserSearchItem(PublicUserCard):
    connection_status: Literal["none", "pending_outgoing", "pending_incoming", "connected"]


class UserSearchResponse(BaseModel):
    users: list[UserSearchItem]


class HandleAvailableResponse(BaseModel):
    available: bool
    reason: Literal["available", "taken", "invalid"] | None = None


class ConnectionRequest(BaseModel):
    handle: str

    @field_validator("handle")
    @classmethod
    def check_handle(cls, value: str) -> str:
        return validate_handle_format(value)


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
    handle: str

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


class IncomingMealTagItem(BaseModel):
    id: uuid.UUID
    tagger: PublicUserCard
    source_dish_name: str | None = None
    source_label: str | None = None
    source_date: datetime.date
    created_at: datetime.datetime


class OutgoingMealTagItem(BaseModel):
    id: uuid.UUID
    tagged_user: PublicUserCard
    status: str
    source_dish_name: str | None = None
    source_label: str | None = None
    source_date: datetime.date
    created_at: datetime.datetime


class MealTagListResponse(BaseModel):
    incoming_pending: list[IncomingMealTagItem]
    outgoing: list[OutgoingMealTagItem]


class PhotoMealTagItem(BaseModel):
    id: uuid.UUID
    user: PublicUserCard
    status: str


class PhotoMealTagListResponse(BaseModel):
    tags: list[PhotoMealTagItem]


class PhotoTagRequest(BaseModel):
    handles: list[str] = Field(default_factory=list, max_length=10)
    group_ids: list[uuid.UUID] = Field(default_factory=list, max_length=5)

    @field_validator("handles")
    @classmethod
    def check_handles(cls, values: list[str]) -> list[str]:
        return [validate_handle_format(v) for v in values]

    @model_validator(mode="after")
    def require_targets(self) -> PhotoTagRequest:
        if not self.handles and not self.group_ids:
            raise ValueError("At least one handle or group_id is required")
        return self
