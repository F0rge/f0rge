from __future__ import annotations

import datetime
from typing import Literal

from pydantic import BaseModel

AuditSource = Literal["books", "nia", "cost"]


class AuditEventItem(BaseModel):
    at: datetime.datetime
    source: AuditSource
    actor: str
    summary: str
    href: str
