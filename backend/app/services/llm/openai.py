from __future__ import annotations

from typing import Any, Optional

from app.services.llm.base import EmbeddingClient, LLMClient


class OpenAIClient(LLMClient):
    """Stub — direct OpenAI SDK integration not yet implemented (use OpenRouter instead)."""

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
        raise NotImplementedError("OpenAIClient is not yet implemented")

    async def complete_with_image(
        self,
        messages: list[dict[str, Any]],
        *,
        model: Optional[str] = None,
    ) -> str:
        raise NotImplementedError("OpenAIClient is not yet implemented")


class OpenAIEmbeddingClient(EmbeddingClient):
    """Stub — direct OpenAI embedding integration not yet implemented (use OpenRouter instead)."""

    def __init__(self, api_key: str, default_model: str) -> None:
        self._api_key = api_key
        self._default_model = default_model

    async def embed(self, text: str, *, model: Optional[str] = None) -> list[float]:
        raise NotImplementedError("OpenAIEmbeddingClient is not yet implemented")

    async def embed_batch(
        self, texts: list[str], *, model: Optional[str] = None
    ) -> list[list[float]]:
        raise NotImplementedError("OpenAIEmbeddingClient is not yet implemented")
