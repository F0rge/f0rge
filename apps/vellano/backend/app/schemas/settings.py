from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class SettingsResponse(BaseModel):
    vat_rate: Decimal
    vat_percent: Decimal
    home_currency: str
    defaults_locked: bool
    warning: Optional[str] = None
    always_prefer_warehouse: bool
    pick_priority: list[uuid.UUID]
    nia_monthly_token_cap: int


class SettingsUpdate(BaseModel):
    vat_rate: Optional[Decimal] = Field(default=None, ge=0, le=1)
    home_currency: Optional[str] = Field(default=None, min_length=3, max_length=3)
    always_prefer_warehouse: Optional[bool] = None
    pick_priority: Optional[list[uuid.UUID]] = None
    nia_monthly_token_cap: Optional[int] = Field(default=None, ge=0)
