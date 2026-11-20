from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class McpTokenCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=80)
    expires_in_days: Literal[7, 30, 90]


class McpTokenRotate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(ge=1, strict=True)


class McpTokenResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    suffix: str
    expires_at: datetime
    last_used_at: Optional[datetime]
    status: Literal["active", "revoked", "expired"]
    version: int


class McpTokenIssued(BaseModel):
    token: McpTokenResponse
    secret: str


class McpTokenActivityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    action: Literal[
        "generated",
        "rotated",
        "revoked",
        "catalogue_searched",
        "actions_found",
        "action_read",
        "write_requested",
        "write_replayed",
        "write_confirmed",
    ]
    action_name: Optional[str]
    operation_id: Optional[uuid.UUID]
    source: Literal["firstout", "mcp"]
    token_name: str
    # A route write records "started" before it runs, then exactly one outcome. "unknown"
    # means the route gave no usable answer, so the change may or may not have been made.
    result: Literal["success", "denied", "failed", "started", "unknown"]
    occurred_at: datetime


class McpAccessResponse(BaseModel):
    endpoint: str
    tokens: list[McpTokenResponse]
    activity: list[McpTokenActivityResponse]
