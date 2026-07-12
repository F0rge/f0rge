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


class ExtractedTreatmentCandidate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    type: TREATMENT_TYPES = "prescription"
    start_date: Optional[datetime.date] = None
    end_date: Optional[datetime.date] = None
    dose: Optional[str] = Field(default=None, max_length=500)
    doses_per_day: Optional[int] = Field(default=None, ge=1, le=12)
    notes: Optional[str] = None
    group_name: Optional[str] = Field(default=None, max_length=100)

    _clean_group_name = field_validator("group_name")(_clean_group_name)

    @field_validator("start_date", mode="before")
    @classmethod
    def _default_start_date(cls, v: object) -> datetime.date:
        if v is None or v == "":
            return local_today()
        if isinstance(v, str):
            return datetime.date.fromisoformat(v)
        if isinstance(v, datetime.date):
            return v
        raise ValueError(f"start_date must be a date, got {type(v)}")

    @field_validator("end_date", mode="before")
    @classmethod
    def _optional_end_date(cls, v: object) -> Optional[datetime.date]:
        if v is None or v == "":
            return None
        if isinstance(v, str):
            return datetime.date.fromisoformat(v)
        if isinstance(v, datetime.date):
            return v
        raise ValueError(f"end_date must be a date or null, got {type(v)}")


class ExtractedTreatmentsPayload(BaseModel):
    treatments: list[ExtractedTreatmentCandidate] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)

    model_config = ConfigDict(strict=True, extra="forbid")


class TreatmentExtractionResult(BaseModel):
    payload: ExtractedTreatmentsPayload
    raw_response: str
    model: str
    attempts: int
    retried_due_to: list[str] = Field(default_factory=list)


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
