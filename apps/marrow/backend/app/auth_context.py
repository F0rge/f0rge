from __future__ import annotations

import uuid
from contextvars import ContextVar

user_id_ctx: ContextVar[uuid.UUID | None] = ContextVar("user_id", default=None)
