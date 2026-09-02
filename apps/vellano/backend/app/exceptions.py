from __future__ import annotations

from f0rge_core.exceptions import DomainError


class ForbiddenError(DomainError):
    """Caller lacks a required permission. Mapped to HTTP 403."""


class NiaLlmUnconfiguredError(DomainError):
    """OpenRouter key missing. Mapped to HTTP 503 with code nia_llm_unconfigured."""

    def __init__(self) -> None:
        super().__init__("nia_llm_unconfigured")


class NiaCapExceededError(DomainError):
    """Monthly token cap reached or blocked (cap 0). Mapped to HTTP 429."""

    def __init__(self) -> None:
        super().__init__("nia_cap_exceeded")
