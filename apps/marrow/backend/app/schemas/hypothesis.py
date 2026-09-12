from __future__ import annotations

import datetime
import re
import uuid
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

HYPOTHESIS_STATUS = Literal["live", "weakening", "killed", "parked"]
HYPOTHESIS_LAYER = Literal[1, 2]

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")


def _normalize_slug(value: str) -> str:
    slug = value.strip().lower()
    if not _SLUG_RE.match(slug):
        raise ValueError("slug must be lowercase letters, digits, and hyphens (max 63)")
    return slug


def _blank_to_none(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


class HypothesisCreate(BaseModel):
    slug: str = Field(min_length=1, max_length=63)
    title: str = Field(min_length=1, max_length=200)
    status: HYPOTHESIS_STATUS = "live"
    layer: Optional[HYPOTHESIS_LAYER] = None
    kill_test: Optional[str] = Field(default=None, max_length=4000)
    next_move: Optional[str] = Field(default=None, max_length=4000)
    last_evidence: Optional[str] = Field(default=None, max_length=4000)
    cite: Optional[str] = Field(default=None, max_length=2000)
    sort_order: int = Field(default=0, ge=0, le=10000)

    _normalize_slug = field_validator("slug")(_normalize_slug)
    _blank_kill_test = field_validator("kill_test")(_blank_to_none)
    _blank_next_move = field_validator("next_move")(_blank_to_none)
    _blank_last_evidence = field_validator("last_evidence")(_blank_to_none)
    _blank_cite = field_validator("cite")(_blank_to_none)


class HypothesisUpdate(BaseModel):
    slug: Optional[str] = Field(default=None, min_length=1, max_length=63)
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    status: Optional[HYPOTHESIS_STATUS] = None
    layer: Optional[HYPOTHESIS_LAYER] = None
    kill_test: Optional[str] = Field(default=None, max_length=4000)
    next_move: Optional[str] = Field(default=None, max_length=4000)
    last_evidence: Optional[str] = Field(default=None, max_length=4000)
    cite: Optional[str] = Field(default=None, max_length=2000)
    sort_order: Optional[int] = Field(default=None, ge=0, le=10000)

    @field_validator("slug")
    @classmethod
    def _normalize_optional_slug(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return _normalize_slug(value)

    _blank_kill_test = field_validator("kill_test")(_blank_to_none)
    _blank_next_move = field_validator("next_move")(_blank_to_none)
    _blank_last_evidence = field_validator("last_evidence")(_blank_to_none)
    _blank_cite = field_validator("cite")(_blank_to_none)


class HypothesisResponse(BaseModel):
    id: uuid.UUID
    slug: str
    title: str
    status: HYPOTHESIS_STATUS
    layer: Optional[HYPOTHESIS_LAYER] = None
    kill_test: Optional[str] = None
    next_move: Optional[str] = None
    last_evidence: Optional[str] = None
    cite: Optional[str] = None
    sort_order: int
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class NOf1Upsert(BaseModel):
    change: str = Field(min_length=1, max_length=2000)
    start: datetime.date
    watch_field: str = Field(min_length=1, max_length=200)
    stop_rule: str = Field(min_length=1, max_length=2000)


class NOf1Response(BaseModel):
    id: uuid.UUID
    change: str
    start: datetime.date
    watch_field: str
    stop_rule: str
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)
