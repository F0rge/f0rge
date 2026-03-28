from __future__ import annotations

import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class PhotoResponse(BaseModel):
    id: int
    entry_id: int
    filename: str
    label: Optional[str] = None
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)
