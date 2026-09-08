from __future__ import annotations

import datetime
import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.books_event import BooksDocumentType, BooksEventAction


class BooksEventResponse(BaseModel):
    id: uuid.UUID
    document_type: BooksDocumentType
    document_id: uuid.UUID
    action: BooksEventAction
    actor_user_id: Optional[uuid.UUID]
    actor_email: Optional[str] = None
    note: Optional[str] = Field(default=None, max_length=512)
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)
