from __future__ import annotations

import datetime
import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class BankRuleCreate(BaseModel):
    bank_account_id: uuid.UUID
    pattern: str = Field(min_length=1, max_length=128)
    target_account_id: uuid.UUID


class BankRuleUpdate(BaseModel):
    pattern: Optional[str] = Field(default=None, min_length=1, max_length=128)
    target_account_id: Optional[uuid.UUID] = None
    is_active: Optional[bool] = None


class BankRuleResponse(BaseModel):
    id: uuid.UUID
    bank_account_id: uuid.UUID
    pattern: str
    target_account_id: uuid.UUID
    is_active: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)
