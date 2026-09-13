from __future__ import annotations

import datetime
import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.books_period import BooksPeriodStatus


class BooksPeriodCreate(BaseModel):
    period_from: datetime.date
    period_to: datetime.date


class BooksPeriodReopen(BaseModel):
    reason: str = Field(min_length=1, max_length=512)


class BooksPeriodResponse(BaseModel):
    id: uuid.UUID
    period_from: datetime.date
    period_to: datetime.date
    status: BooksPeriodStatus
    locked_at: Optional[datetime.datetime]
    locked_by_user_id: Optional[uuid.UUID]
    reopen_reason: Optional[str]
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)
