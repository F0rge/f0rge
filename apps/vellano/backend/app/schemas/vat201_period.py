from __future__ import annotations

import datetime
import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.vat201_period import Vat201PeriodStatus
from app.schemas.bank_import import Vat201Draft


class Vat201PeriodCreate(BaseModel):
    period_from: datetime.date
    period_to: datetime.date


class Vat201PeriodReopen(BaseModel):
    reason: str = Field(min_length=1, max_length=512)


class Vat201PeriodResponse(BaseModel):
    id: uuid.UUID
    period_from: datetime.date
    period_to: datetime.date
    status: Vat201PeriodStatus
    locked_at: Optional[datetime.datetime]
    locked_by_user_id: Optional[uuid.UUID]
    reopen_reason: Optional[str]
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class Vat201PeriodDetailResponse(Vat201PeriodResponse):
    draft: Vat201Draft
