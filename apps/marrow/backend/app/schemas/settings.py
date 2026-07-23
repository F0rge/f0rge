from __future__ import annotations

import re
from typing import Literal, Optional

from pydantic import BaseModel, field_validator

_CATALOG_KEY_RE = re.compile(r"^[a-z0-9_]+$")


class SettingsResponse(BaseModel):
    """Public view of user settings. Never exposes plaintext keys or encrypted bytes."""

    llm_provider: str
    llm_model: Optional[str]
    embedding_provider: str
    embedding_model: Optional[str]
    has_api_key: bool
    has_external_api_token: bool
    onboarding_completed: bool
    tagged_meal_mode: str = "approve"
    profile_tag_filter_mode: str = "off"
    profile_filter_tags: list[str] = []
    default_supplements: list[str] = []
    default_symptoms: dict[str, int] = {}


class LLMSettingsUpdate(BaseModel):
    """Incoming update for LLM settings. api_key is plaintext in, never out.

    llm_api_key is the single stored BYOK key — it is also used by the embedding
    client (see app/services/llm/factory.py resolve_embedding_credentials)."""

    llm_provider: Optional[str] = None
    llm_api_key: Optional[str] = None
    llm_model: Optional[str] = None


class EmbeddingSettingsUpdate(BaseModel):
    """Incoming update for embedding settings. Key is set via the LLM endpoint —
    there is only one stored BYOK key, shared by both clients."""

    embedding_provider: Optional[str] = None
    embedding_model: Optional[str] = None


class TestConnectionResponse(BaseModel):
    ok: bool
    detail: Optional[str] = None


class ExternalTokenResponse(BaseModel):
    """Plaintext token returned once on generation. Never returned by GET.
    Store it immediately — it cannot be recovered after this response."""

    token: str


class TaggedMealModeUpdate(BaseModel):
    tagged_meal_mode: str

    @field_validator("tagged_meal_mode")
    @classmethod
    def validate_mode(cls, value: str) -> str:
        if value not in ("approve", "auto"):
            raise ValueError("tagged_meal_mode must be 'approve' or 'auto'")
        return value


class ProfileTagFilterUpdate(BaseModel):
    profile_tag_filter_mode: Literal["off", "hide", "show_only"]
    profile_filter_tags: list[str] = []


class CheckinDefaultsUpdate(BaseModel):
    default_supplements: list[str] = []
    default_symptoms: dict[str, int] = {}

    @field_validator("default_supplements", mode="after")
    @classmethod
    def validate_default_supplements(cls, v: list[str]) -> list[str]:
        for key in v:
            if not key:
                continue
            if not _CATALOG_KEY_RE.match(key):
                raise ValueError("supplement key must match ^[a-z0-9_]+$")
        return v

    @field_validator("default_symptoms", mode="after")
    @classmethod
    def validate_default_symptoms(cls, v: dict[str, int]) -> dict[str, int]:
        for key, value in v.items():
            if not _CATALOG_KEY_RE.match(key):
                raise ValueError("symptom key must match ^[a-z0-9_]+$")
            if not isinstance(value, int):
                raise ValueError("severity must be integer 0-10")
            if not 0 <= value <= 10:
                raise ValueError("severity must be integer 0-10")
        return v


class TokenRevokedResponse(BaseModel):
    revoked: bool = True
