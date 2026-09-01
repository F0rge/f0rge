from __future__ import annotations

from f0rge_core.exceptions import DomainError


class ForbiddenError(DomainError):
    """Caller lacks a required permission. Mapped to HTTP 403."""
