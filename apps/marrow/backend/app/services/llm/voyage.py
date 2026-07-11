from __future__ import annotations

from typing import Any, Optional

from app.services.llm.base import EmbeddingClient, LLMClient


class VoyageClient(LLMClient):
    """Stub — Voyage AI LLM integration not yet implemented."""

    def __init__(self, api_key: str, default_model: str) -> None:
        self._api_key = api_key
        self._default_model = default_model

    async def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        response_format: Optional[dict[str, str]] = None,
        temperature: float = 0.0,
        max_tokens: int = 8192,
        model: Optional[str] = None,
    ) -> str:
        raise NotImplementedError("VoyageClient is not yet implemented")

    async def complete_with_image(
        self,
        messages: list[dict[str, Any]],
        *,
        model: Optional[str] = None,
    ) -> str:
        raise NotImplementedError("VoyageClient is not yet implemented")


class VoyageEmbeddingClient(EmbeddingClient):
    """Stub — Voyage AI embedding integration not yet implemented."""

    def __init__(self, api_key: str, default_model: str) -> None:
        self._api_key = api_key
        self._default_model = default_model

    async def embed(self, text: str, *, model: Optional[str] = None) -> list[float]:
        raise NotImplementedError("VoyageEmbeddingClient is not yet implemented")

    async def embed_batch(
        self, texts: list[str], *, model: Optional[str] = None
    ) -> list[list[float]]:
        raise NotImplementedError("VoyageEmbeddingClient is not yet implemented")
