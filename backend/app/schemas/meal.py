from __future__ import annotations

import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class RecentMealResponse(BaseModel):
    """A distinct previously-logged meal, offered for one-tap re-logging.

    Deduped by ``dish_name``; ``source_photo_id`` is the most-recent instance's
    photo, i.e. the concrete meal that ``clone`` will copy.
    """

    dish_name: str
    source_photo_id: int
    times_logged: int
    last_logged: datetime.date
    diet_flags: list[str] = []

    model_config = ConfigDict(from_attributes=True)


class MealCloneCreate(BaseModel):
    source_photo_id: int
    meal_time: Optional[datetime.datetime] = None

    @field_validator("meal_time", mode="after")
    @classmethod
    def strip_meal_time_tz(cls, v: Optional[datetime.datetime]) -> Optional[datetime.datetime]:
        # Postgres column is TIMESTAMP WITHOUT TIME ZONE; asyncpg refuses to
        # bind an offset-aware datetime to it. Convert to UTC then drop tzinfo.
        # Same normalization as PhotoMealTimeUpdate.
        if v is None or v.tzinfo is None:
            return v
        utc_offset = v.utcoffset()
        naive_utc = (v - utc_offset).replace(tzinfo=None)
        return naive_utc
