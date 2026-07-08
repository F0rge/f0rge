from __future__ import annotations

import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class TreatmentLogUpdate(BaseModel):
    date: datetime.date
    doses_taken: int


class TreatmentLogResponse(BaseModel):
    treatment_id: int
    date: datetime.date
    doses_taken: int
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class ProtocolItem(BaseModel):
    id: int
    name: str
    dose: Optional[str] = None
    doses_per_day: Optional[int] = None
    doses_taken: int
    day_num: int


class ProtocolToday(BaseModel):
    doses_taken: int
    doses_planned: int
    pct: float


class ProtocolResponse(BaseModel):
    items: list[ProtocolItem]
    today: ProtocolToday
    streak: int
    best_streak: int
