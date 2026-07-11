from __future__ import annotations

import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

LAB_TYPES = Literal[
    "blood",
    "breath",
    "imaging",
    "microbiology",
    "allergy",
    "comprehensive",
    "other",
]

REVIEW_STATUSES = Literal["confirmed", "needs_review"]


class LabMarkerCreate(BaseModel):
    catalog_id: int
    canonical_name: str = Field(min_length=1, max_length=200)
    display_name: str = Field(min_length=1, max_length=200)
    value: Optional[float] = None
    value_text: Optional[str] = Field(default=None, max_length=200)
    unit: Optional[str] = Field(default=None, max_length=40)
    ref_low: Optional[float] = None
    ref_high: Optional[float] = None
    ref_text: Optional[str] = Field(default=None, max_length=100)


class LabMarkerResponse(BaseModel):
    id: int
    catalog_id: int
    canonical_name: str
    display_name: str
    value: Optional[float] = None
    value_text: Optional[str] = None
    unit: Optional[str] = None
    ref_low: Optional[float] = None
    ref_high: Optional[float] = None
    ref_text: Optional[str] = None
    flag: str

    model_config = ConfigDict(from_attributes=True)


class LabCreate(BaseModel):
    lab_date: datetime.date
    name: str = Field(min_length=1, max_length=200)
    type: LAB_TYPES
    lab_location: Optional[str] = Field(default=None, max_length=200)
    source_kind: str = Field(default="text")
    source_path: Optional[str] = None
    attachment_path: Optional[str] = None
    raw_text: Optional[str] = None
    notes: Optional[str] = None
    markers: List[LabMarkerCreate] = Field(default_factory=list)


class LabUpdate(BaseModel):
    lab_date: Optional[datetime.date] = None
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    type: Optional[LAB_TYPES] = None
    lab_location: Optional[str] = Field(default=None, max_length=200)
    notes: Optional[str] = None
    review_status: Optional[REVIEW_STATUSES] = None
    markers: Optional[List[LabMarkerCreate]] = None


class LabResponse(BaseModel):
    id: int
    lab_date: datetime.date
    name: str
    type: str
    lab_location: Optional[str] = None
    source_kind: str
    source_path: Optional[str] = None
    attachment_path: Optional[str] = None
    extraction_model: Optional[str] = None
    extraction_confidence: Optional[float] = None
    review_status: str
    notes: Optional[str] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime
    markers: List[LabMarkerResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class LabExtractRequest(BaseModel):
    document_text: str = Field(min_length=1)


class LabImportRequest(BaseModel):
    document_text: str = Field(min_length=1)
    source_path: Optional[str] = None
    force: bool = False
