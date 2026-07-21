from __future__ import annotations

import datetime
import uuid

from pydantic import BaseModel, Field


class DeviceRegisterRequest(BaseModel):
    token: str = Field(min_length=1)
    platform: str = "ios"


class DeviceTokenResponse(BaseModel):
    id: uuid.UUID
    token: str
    platform: str
    created_at: datetime.datetime

    model_config = {"from_attributes": True}
