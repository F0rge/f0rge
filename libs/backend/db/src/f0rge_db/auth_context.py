from __future__ import annotations

import uuid
from contextvars import ContextVar

# The single process-wide authenticated-user ContextVar. Every consumer must
# import THIS instance — a second surviving copy elsewhere means a silent RLS
# bypass (the GUC hooks would read the wrong ContextVar).
user_id_ctx: ContextVar[uuid.UUID | None] = ContextVar("user_id", default=None)
