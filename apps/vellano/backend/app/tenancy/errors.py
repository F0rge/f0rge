from __future__ import annotations

import uuid
from dataclasses import dataclass

from f0rge_core.exceptions import NotFoundError, UnauthorizedError


@dataclass(frozen=True)
class TenantContext:
    id: uuid.UUID
    slug: str
    database_url: str
    storage_prefix: str


class TenantNotFoundError(NotFoundError):
    def __init__(self) -> None:
        super().__init__("tenant_not_found")


class TenantMismatchError(UnauthorizedError):
    def __init__(self) -> None:
        super().__init__("Invalid session")
