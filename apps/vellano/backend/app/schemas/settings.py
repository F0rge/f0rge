from __future__ import annotations

from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class SettingsResponse(BaseModel):
    vat_rate: Decimal
    vat_percent: Decimal
    home_currency: str
    defaults_locked: bool
    warning: Optional[str] = None


class SettingsUpdate(BaseModel):
    vat_rate: Optional[Decimal] = Field(default=None, ge=0, le=1)
    home_currency: Optional[str] = Field(default=None, min_length=3, max_length=3)
