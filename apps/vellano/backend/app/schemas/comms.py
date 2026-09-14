from __future__ import annotations

import datetime
import uuid
from typing import Optional

from pydantic import BaseModel


class CommsMessageResponse(BaseModel):
    id: uuid.UUID
    created_at: datetime.datetime
    sent_at: Optional[datetime.datetime] = None
    channel: str
    provider: str
    document_type: str
    document_id: uuid.UUID
    to_address: str
    from_identity: str
    status: str
    provider_message_id: Optional[str] = None
    error: Optional[str] = None
