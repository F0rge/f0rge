from __future__ import annotations

import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.utils.dates import local_today

TREATMENT_TYPES = Literal[
    "antibiotic",
    "antimicrobial",
    "prescription",
    "intervention",
    "protocol",
    "other",
]


class TreatmentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    type: TREATMENT_TYPES
    start_date: datetime.date
    end_date: Optional[datetime.date] = None
    dose: Optional[str] = Field(default=None, max_length=500)
    notes: Optional[str] = None


class TreatmentUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    type: Optional[TREATMENT_TYPES] = None
    start_date: Optional[datetime.date] = None
    end_date: Optional[datetime.date] = None
    dose: Optional[str] = Field(default=None, max_length=500)
    notes: Optional[str] = None


class TreatmentResponse(BaseModel):
    id: int
    name: str
    normalized_name: str
    type: TREATMENT_TYPES
    start_date: datetime.date
    end_date: Optional[datetime.date] = None
    dose: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime

    @computed_field
    @property
    def is_active(self) -> bool:
        return self.end_date is None or self.end_date >= local_today()

    model_config = ConfigDict(from_attributes=True)
