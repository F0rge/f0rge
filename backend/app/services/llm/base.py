from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional


class LLMClient(ABC):
    """Stateless chat-completion client."""

    @abstractmethod
    async def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        response_format: Optional[dict[str, str]] = None,
        temperature: float = 0.0,
        max_tokens: int = 8192,
        model: Optional[str] = None,
    ) -> str:
        """Return the assistant message content as a string."""
        ...

    @abstractmethod
    async def complete_with_image(
        self,
        messages: list[dict[str, Any]],
        *,
        model: Optional[str] = None,
    ) -> str:
        """
        Multimodal variant. messages must contain at least one image_url content part.
        model overrides the default for callers that need a vision-capable model
        regardless of what the user has configured.
        """
        ...


class EmbeddingClient(ABC):
    """Stateless embedding client. Returns vectors at the configured dimension."""

    @abstractmethod
    async def embed(self, text: str, *, model: Optional[str] = None) -> list[float]:
        """Embed a single string. Returns a list of floats of length == dim."""
        ...

    @abstractmethod
    async def embed_batch(
        self, texts: list[str], *, model: Optional[str] = None
    ) -> list[list[float]]:
        """
        Embed multiple strings in a single API call where the backend supports it.
        Returns a list of vectors in the same order as input.
        """
        ...
