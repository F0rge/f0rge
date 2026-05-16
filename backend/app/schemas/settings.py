from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class SettingsResponse(BaseModel):
    """Public view of user settings. Never exposes plaintext keys or encrypted bytes."""

    llm_provider: str
    llm_model: Optional[str]
    has_llm_api_key: bool
    embedding_provider: str
    embedding_model: Optional[str]
    has_embedding_api_key: bool
    has_external_api_token: bool


class LLMSettingsUpdate(BaseModel):
    """Incoming update for LLM settings. api_key is plaintext in, never out."""

    llm_provider: Optional[str] = None
    llm_api_key: Optional[str] = None
    llm_model: Optional[str] = None


class EmbeddingSettingsUpdate(BaseModel):
    """Incoming update for embedding settings. api_key is plaintext in, never out."""

    embedding_provider: Optional[str] = None
    embedding_api_key: Optional[str] = None
    embedding_model: Optional[str] = None


class TestConnectionResponse(BaseModel):
    ok: bool
    detail: Optional[str] = None
