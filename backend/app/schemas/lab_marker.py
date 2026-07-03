from __future__ import annotations

import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class LabMarkerCatalogCreate(BaseModel):
    canonical_name: str = Field(min_length=1, max_length=200)
    display_name: str = Field(min_length=1, max_length=200)
    common_units: List[str] = Field(default_factory=list)
    description: Optional[str] = None


class LabMarkerCatalogResponse(BaseModel):
    id: int
    canonical_name: str
    display_name: str
    common_units: List[str]
    description: Optional[str] = None
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class LabMarkerAliasCreate(BaseModel):
    alias: str = Field(min_length=1, max_length=200)
    language: Optional[str] = Field(default=None, max_length=10)


class LabMarkerAliasResponse(BaseModel):
    id: int
    catalog_id: int
    alias: str
    language: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class MarkerHistoryPoint(BaseModel):
    lab_date: datetime.date
    value: Optional[float] = None
    value_text: Optional[str] = None
    unit: Optional[str] = None
    ref_low: Optional[float] = None
    ref_high: Optional[float] = None
    flag: str

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Extraction Pydantic models (used by LabExtractionService)
# ---------------------------------------------------------------------------


class CatalogHint(BaseModel):
    canonical: str = Field(min_length=1, max_length=100)
    display: str
    aliases: List[str] = Field(default_factory=list)
    common_units: List[str] = Field(default_factory=list)

    model_config = ConfigDict(strict=True)


class ExtractedMarker(BaseModel):
    canonical_match: Optional[str] = None
    proposed_canonical: Optional[str] = None
    display_name: str = Field(min_length=1, max_length=200)
    value: Optional[float] = None
    value_text: Optional[str] = Field(default=None, max_length=200)
    unit: Optional[str] = Field(default=None, max_length=40)
    ref_low: Optional[float] = None
    ref_high: Optional[float] = None
    ref_text: Optional[str] = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def _exactly_one_canonical(self) -> "ExtractedMarker":
        both_none = self.canonical_match is None and self.proposed_canonical is None
        both_set = self.canonical_match is not None and self.proposed_canonical is not None
        if both_none or both_set:
            raise ValueError("exactly one of canonical_match or proposed_canonical must be set")
        if self.value is None and self.value_text is None:
            raise ValueError("at least one of value or value_text must be set")
        return self


class ExtractedLab(BaseModel):
    lab_date: datetime.date
    name: str = Field(min_length=1, max_length=200)
    type: Literal[
        "blood",
        "breath",
        "imaging",
        "microbiology",
        "allergy",
        "comprehensive",
        "other",
    ]
    lab_location: Optional[str] = Field(default=None, max_length=200)
    notes: Optional[str] = None

    @field_validator("lab_date", mode="before")
    @classmethod
    def _sane_date(cls, v: object) -> datetime.date:
        if isinstance(v, str):
            v = datetime.date.fromisoformat(v)
        if not isinstance(v, datetime.date):
            raise ValueError(f"lab_date must be a date, got {type(v)}")
        today = datetime.date.today()
        if v > today + datetime.timedelta(days=1) or v.year < 1900:
            raise ValueError(f"lab_date out of range: {v}")
        return v


class ExtractedLabPayload(BaseModel):
    lab: ExtractedLab
    markers: List[ExtractedMarker]
    confidence: float = Field(ge=0.0, le=1.0)

    model_config = ConfigDict(strict=True, extra="forbid")


class ExtractionResult(BaseModel):
    payload: ExtractedLabPayload
    raw_response: str
    model: str
    attempts: int
    retried_due_to: List[str] = Field(default_factory=list)
