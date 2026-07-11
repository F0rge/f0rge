from __future__ import annotations

import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from app.utils.dates import local_today

TREATMENT_TYPES = Literal[
    "antibiotic",
    "antimicrobial",
    "prescription",
    "intervention",
    "protocol",
    "other",
]

TREATMENT_END_REASONS = {
    "completed",
    "side_effects",
    "ineffective",
    "doctor_advised",
    "switched",
    "other",
}


def _clean_group_name(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _validate_end_reason(value: Optional[str]) -> Optional[str]:
    if value is not None and value not in TREATMENT_END_REASONS:
        raise ValueError(f"end_reason must be one of {sorted(TREATMENT_END_REASONS)} or null")
    return value


class TreatmentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    type: TREATMENT_TYPES
    start_date: datetime.date
    end_date: Optional[datetime.date] = None
    end_reason: Optional[str] = None
    end_note: Optional[str] = Field(default=None, max_length=1000)
    dose: Optional[str] = Field(default=None, max_length=500)
    doses_per_day: Optional[int] = Field(default=None, ge=1, le=12)
    notes: Optional[str] = None
    group_name: Optional[str] = Field(default=None, max_length=100)

    _clean_group_name = field_validator("group_name")(_clean_group_name)
    _validate_end_reason = field_validator("end_reason")(_validate_end_reason)


class TreatmentUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    type: Optional[TREATMENT_TYPES] = None
    start_date: Optional[datetime.date] = None
    end_date: Optional[datetime.date] = None
    end_reason: Optional[str] = None
    end_note: Optional[str] = Field(default=None, max_length=1000)
    dose: Optional[str] = Field(default=None, max_length=500)
    doses_per_day: Optional[int] = Field(default=None, ge=1, le=12)
    notes: Optional[str] = None
    group_name: Optional[str] = Field(default=None, max_length=100)

    _clean_group_name = field_validator("group_name")(_clean_group_name)
    _validate_end_reason = field_validator("end_reason")(_validate_end_reason)


class TreatmentResponse(BaseModel):
    id: int
    name: str
    normalized_name: str
    type: TREATMENT_TYPES
    start_date: datetime.date
    end_date: Optional[datetime.date] = None
    end_reason: Optional[str] = None
    end_note: Optional[str] = None
    dose: Optional[str] = None
    doses_per_day: Optional[int] = None
    notes: Optional[str] = None
    group_name: Optional[str] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime

    @computed_field
    @property
    def is_active(self) -> bool:
        return self.end_date is None or self.end_date >= local_today()

    model_config = ConfigDict(from_attributes=True)
