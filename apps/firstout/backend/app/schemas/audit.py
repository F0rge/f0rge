from __future__ import annotations

import datetime
import uuid
from typing import Literal

from pydantic import BaseModel

AuditSource = Literal["books", "cost", "mcp"]


class AuditEventItem(BaseModel):
    at: datetime.datetime
    source: AuditSource
    actor: str
    summary: str
    href: str | None
    origin: Literal["firstout", "mcp"] | None = None
    token_id: uuid.UUID | None = None
    operation_id: uuid.UUID | None = None
    record_id: uuid.UUID | None = None
