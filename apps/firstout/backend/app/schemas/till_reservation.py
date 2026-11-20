from __future__ import annotations

import datetime
import uuid
from typing import Optional

from pydantic import BaseModel


class BlockingReservation(BaseModel):
    """The soonest-freeing live reservation; names the showroom, never the person."""

    location_id: uuid.UUID
    location_name: str
    holder_kind: str
    expires_at: Optional[datetime.datetime]


class TillReservation(BaseModel):
    sku_id: uuid.UUID
    reserved_by_others: int
    blocking: Optional[BlockingReservation]
