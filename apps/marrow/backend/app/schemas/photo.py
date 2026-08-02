from __future__ import annotations

import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class PhotoResponse(BaseModel):
    id: int
    entry_id: int
    meal_id: int | None = None
    filename: Optional[str] = None
    has_image: bool = True
    icon_key: Optional[str] = None
    label: Optional[str] = None
    # AI dish name from the meal's analysis; `label` stays the user-facing override.
    # Populated by PhotoService.list_photos only — see the note there.
    dish_name: Optional[str] = None
    meal_time: Optional[datetime.datetime] = None
    created_at: datetime.datetime
    hidden_at: Optional[datetime.datetime] = None
    # Explicit per-photo tags (photo_diet_tags keys) vs server-derived flags
    # computed from the confirmed analysis (diet_flags.compute_signal_from_analyses).
    diet_tags: list[str] = []
    derived_diet_tags: list[str] = []
    source_photo_id: Optional[int] = None
    tagged_by_handle: Optional[str] = None
    tagged_with_handles: list[str] = []

    model_config = ConfigDict(from_attributes=True)


class PhotoUpdate(BaseModel):
    label: Optional[str] = None
    meal_time: Optional[datetime.datetime] = None
    hidden: Optional[bool] = None
    diet_tags: Optional[list[str]] = None

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
