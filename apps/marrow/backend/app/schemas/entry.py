from __future__ import annotations

import datetime
import re
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.photo import PhotoResponse
from app.services.diet_flags import PhotoSignal

_SYMPTOM_KEY_RE = re.compile(r"^[a-z0-9_]+$")
_STOOL_COMPLETENESS_VALUES = {"complete", "incomplete"}


def _validate_stool_completeness(value: Optional[str]) -> Optional[str]:
    if value is not None and value not in _STOOL_COMPLETENESS_VALUES:
        raise ValueError("stool_completeness must be 'complete', 'incomplete', or null")
    return value


class MedicationIntake(BaseModel):
    key: str = Field(min_length=1, max_length=64)
    dose: Optional[str] = None
    reason: Optional[str] = None
    time: Optional[str] = None  # wall-clock "HH:MM" display string, no tz logic


class EntryCreate(BaseModel):
    date: datetime.date
    # v4 = 5-point core scales (overall/sleep_quality/stress/neuro) + stool_completeness.
    # Existing rows keep whatever schema_version they were written with -- this default
    # only affects newly-created entries.
    schema_version: Optional[int] = 4
    entry_time: Optional[datetime.datetime] = None
    period_of_day: Optional[str] = None
    overall: int
    bloating: int
    # v1 fields (optional; v2 clients should send stool_status / bristol_type)
    stool_normal: Optional[bool] = None
    stool_type: Optional[str] = None
    stool_status: Optional[str] = Field(
        default=None,
        description="v2: 'normal' | 'abnormal' | 'none'",
    )
    bristol_type: Optional[int] = Field(default=None, ge=1, le=7)
    stool_completeness: Optional[str] = Field(
        default=None,
        description="v4: 'complete' | 'incomplete'",
    )
    joint_pain: int = 0
    neuro: int = 0
    sleep_quality: int
    stress: int
    diet_risk: str
    supplements: str
    sick: bool
    hot_shower: Optional[bool] = False
    alcohol_units: Optional[int] = Field(default=None, ge=0, le=10)
    caffeine_servings: Optional[int] = Field(default=None, ge=0, le=10)
    notes: Optional[str] = None
    symptoms_json: Optional[dict] = None
    medications: list[MedicationIntake] = Field(default_factory=list)

    _validate_stool_completeness = field_validator("stool_completeness")(
        _validate_stool_completeness
    )

    @field_validator("entry_time", mode="after")
    @classmethod
    def strip_entry_time_tz(cls, v: Optional[datetime.datetime]) -> Optional[datetime.datetime]:
        # Postgres column is TIMESTAMP WITHOUT TIME ZONE; asyncpg refuses to
        # bind an offset-aware datetime to it. Convert to UTC then drop tzinfo.
        if v is None or v.tzinfo is None:
            return v
        utc_offset = v.utcoffset()
        naive_utc = (v - utc_offset).replace(tzinfo=None)
        return naive_utc

    @field_validator("symptoms_json", mode="after")
    @classmethod
    def validate_symptoms_json(cls, v: Optional[dict]) -> Optional[dict]:
        if v is None:
            return v
        for key, value in v.items():
            if not _SYMPTOM_KEY_RE.match(key):
                raise ValueError("symptom key must match ^[a-z0-9_]+$")
            if not isinstance(value, int):
                raise ValueError("severity must be integer 0-10")
            if not 0 <= value <= 10:
                raise ValueError("severity must be integer 0-10")
        return v


class EntryUpdate(BaseModel):
    schema_version: Optional[int] = None
    # entry_time/period_of_day are accepted here for shape-parity with EntryCreate (and to
    # keep the tz-strip validator below applying uniformly), but the service always
    # re-stamps both to "now" on every update -- they are server-owned last-edited
    # metadata, not a caller-settable field. See EntriesService.update_entry.
    entry_time: Optional[datetime.datetime] = None
    period_of_day: Optional[str] = None
    overall: Optional[int] = None
    bloating: Optional[int] = None
    stool_normal: Optional[bool] = None
    stool_type: Optional[str] = None
    stool_status: Optional[str] = None
    bristol_type: Optional[int] = Field(default=None, ge=1, le=7)
    stool_completeness: Optional[str] = None
    joint_pain: Optional[int] = None
    neuro: Optional[int] = None
    sleep_quality: Optional[int] = None
    stress: Optional[int] = None
    diet_risk: Optional[str] = None
    supplements: Optional[str] = None
    sick: Optional[bool] = None
    hot_shower: Optional[bool] = None
    alcohol_units: Optional[int] = Field(default=None, ge=0, le=10)
    caffeine_servings: Optional[int] = Field(default=None, ge=0, le=10)
    notes: Optional[str] = None
    symptoms_json: Optional[dict] = None
    medications: Optional[list[MedicationIntake]] = None

    _validate_stool_completeness = field_validator("stool_completeness")(
        _validate_stool_completeness
    )

    @field_validator("entry_time", mode="after")
    @classmethod
    def strip_entry_time_tz(cls, v: Optional[datetime.datetime]) -> Optional[datetime.datetime]:
        # Same fix as EntryCreate — strip tz so asyncpg can bind to
        # TIMESTAMP WITHOUT TIME ZONE.
        if v is None or v.tzinfo is None:
            return v
        utc_offset = v.utcoffset()
        naive_utc = (v - utc_offset).replace(tzinfo=None)
        return naive_utc

    @field_validator("symptoms_json", mode="after")
    @classmethod
    def validate_symptoms_json(cls, v: Optional[dict]) -> Optional[dict]:
        if v is None:
            return v
        for key, value in v.items():
            if not _SYMPTOM_KEY_RE.match(key):
                raise ValueError("symptom key must match ^[a-z0-9_]+$")
            if not isinstance(value, int):
                raise ValueError("severity must be integer 0-10")
            if not 0 <= value <= 10:
                raise ValueError("severity must be integer 0-10")
        return v


class EntryResponse(BaseModel):
    id: int
    date: datetime.date
    schema_version: int
    entry_time: Optional[datetime.datetime] = None
    period_of_day: Optional[str] = None
    overall: int
    bloating: int
    stool_normal: Optional[bool] = None
    stool_type: Optional[str] = None
    stool_status: Optional[str] = None
    bristol_type: Optional[int] = None
    stool_completeness: Optional[str] = None
    joint_pain: int
    neuro: int
    sleep_quality: int
    stress: int
    diet_risk: str
    supplements: str
    sick: bool
    hot_shower: bool = False
    alcohol_units: Optional[int] = None
    caffeine_servings: Optional[int] = None
    notes: Optional[str] = None
    symptoms_json: dict = Field(default_factory=dict)
    medications: list[MedicationIntake] = Field(default_factory=list)
    photos: list[PhotoResponse] = []
    created_at: datetime.datetime
    updated_at: datetime.datetime
    # Computed fields — not stored in DB; populated by the service on every read.
    effective_flags: list[str] = Field(default_factory=list)
    photo_derived_flags: list[str] = Field(default_factory=list)
    user_added_flags: list[str] = Field(default_factory=list)
    photo_signal: PhotoSignal

    model_config = ConfigDict(from_attributes=True)
