from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.account import AccountType, TaxTreatment


class AccountCreate(BaseModel):
    code: str = Field(min_length=1, max_length=16)
    name: str = Field(min_length=1)
    type: AccountType
    tax_treatment: Optional[TaxTreatment] = None


class AccountUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1)
    is_archived: Optional[bool] = None
    tax_treatment: Optional[TaxTreatment] = None


class AccountResponse(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    type: AccountType
    is_system: bool
    is_archived: bool
    tax_treatment: TaxTreatment
    balance_zar: Decimal
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)
