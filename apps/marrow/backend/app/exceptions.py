from __future__ import annotations


class DomainError(Exception):
    """Base class for domain exceptions raised by services.

    Services raise these instead of constructing HTTPException directly.
    Global handlers registered in ``app/main.py`` map each subclass to a
    matching HTTP response, keeping routers free of branching logic.
    """

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class NotFoundError(DomainError):
    """Resource does not exist. Mapped to HTTP 404."""


class ValidationError(DomainError):
    """Request data fails domain validation. Mapped to HTTP 400."""


class ConflictError(DomainError):
    """Operation conflicts with existing state. Mapped to HTTP 409."""


class UnauthorizedError(DomainError):
    """Authentication failed or session invalid. Mapped to HTTP 401."""


class ExternalServiceError(DomainError):
    """Upstream service (weather API, LLM, etc.) failed. Mapped to HTTP 502."""
