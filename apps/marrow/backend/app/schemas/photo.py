from __future__ import annotations

import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class PhotoResponse(BaseModel):
    id: int
    entry_id: int
    filename: str
    label: Optional[str] = None
    meal_time: Optional[datetime.datetime] = None
    created_at: datetime.datetime
    source_photo_id: Optional[int] = None
    tagged_by_handle: Optional[str] = None
    tagged_with_handles: list[str] = []

    model_config = ConfigDict(from_attributes=True)


class PhotoUpdate(BaseModel):
    label: Optional[str] = None
    meal_time: Optional[datetime.datetime] = None

    @field_validator("meal_time", mode="after")
    @classmethod
    def strip_meal_time_tz(cls, v: Optional[datetime.datetime]) -> Optional[datetime.datetime]:
        # Postgres column is TIMESTAMP WITHOUT TIME ZONE; asyncpg refuses to
        # bind an offset-aware datetime to it. Convert to UTC then drop tzinfo.
        if v is None or v.tzinfo is None:
            return v
        utc_offset = v.utcoffset()
        naive_utc = (v - utc_offset).replace(tzinfo=None)
        return naive_utc
