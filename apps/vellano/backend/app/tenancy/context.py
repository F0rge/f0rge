from __future__ import annotations

from contextvars import ContextVar
from typing import Optional

from app.tenancy.errors import TenantContext

tenant_ctx: ContextVar[Optional[TenantContext]] = ContextVar("tenant_ctx", default=None)
