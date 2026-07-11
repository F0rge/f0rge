from __future__ import annotations

from typing import Any, Optional

import httpx

from app.exceptions import ExternalServiceError
from app.services.llm.base import EmbeddingClient, LLMClient

_COMPLETIONS_URL = "https://openrouter.ai/api/v1/chat/completions"
_EMBEDDINGS_URL = "https://openrouter.ai/api/v1/embeddings"
_EMBEDDING_DIM = 1024


async def _post(
    url: str, *, api_key: str, payload: dict[str, Any], timeout: float
) -> dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(url, headers=headers, json=payload)
    if resp.status_code >= 400:
        raise ExternalServiceError(f"Upstream LLM error: {resp.status_code} {resp.text[:200]}")
    return resp.json()


class OpenRouterClient(LLMClient):
    """LLM client backed by OpenRouter's chat completions endpoint."""

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
        payload: dict[str, Any] = {
            "model": model or self._default_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format is not None:
            payload["response_format"] = response_format
        data = await _post(_COMPLETIONS_URL, api_key=self._api_key, payload=payload, timeout=90.0)
        return data["choices"][0]["message"]["content"]

    async def complete_with_image(
        self,
        messages: list[dict[str, Any]],
        *,
        model: Optional[str] = None,
    ) -> str:
        # Image messages are standard messages with image_url content parts;
        # the completions endpoint handles them identically.
        payload: dict[str, Any] = {
            "model": model or self._default_model,
            "messages": messages,
        }
        data = await _post(_COMPLETIONS_URL, api_key=self._api_key, payload=payload, timeout=60.0)
        return data["choices"][0]["message"]["content"]


class OpenRouterEmbeddingClient(EmbeddingClient):
    """Embedding client backed by OpenRouter's embeddings endpoint."""

    def __init__(self, api_key: str, default_model: str) -> None:
        self._api_key = api_key
        self._default_model = default_model

    async def embed(self, text: str, *, model: Optional[str] = None) -> list[float]:
        payload = {
            "model": model or self._default_model,
            "input": text,
            "dimensions": _EMBEDDING_DIM,
        }
        data = await _post(_EMBEDDINGS_URL, api_key=self._api_key, payload=payload, timeout=30.0)
        # OpenRouter adds extra top-level fields (provider, id) vs vanilla OpenAI.
        # Access data[0].embedding explicitly — do not assert on key count.
        return data["data"][0]["embedding"]

    async def embed_batch(
        self, texts: list[str], *, model: Optional[str] = None
    ) -> list[list[float]]:
        payload = {
            "model": model or self._default_model,
            "input": texts,
            "dimensions": _EMBEDDING_DIM,
        }
        data = await _post(_EMBEDDINGS_URL, api_key=self._api_key, payload=payload, timeout=60.0)
        # data is ordered by index field, but sort defensively.
        rows = sorted(data["data"], key=lambda d: d["index"])
        return [row["embedding"] for row in rows]
