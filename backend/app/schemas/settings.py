from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class SettingsResponse(BaseModel):
    """Public view of user settings. Never exposes plaintext keys or encrypted bytes."""

    llm_provider: str
    llm_model: Optional[str]
    embedding_provider: str
    embedding_model: Optional[str]
    has_api_key: bool
    has_external_api_token: bool


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


class TokenRevokedResponse(BaseModel):
    revoked: bool = True
