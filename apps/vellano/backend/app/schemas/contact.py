from __future__ import annotations

import uuid
from typing import Literal, Optional

from pydantic import BaseModel, Field


class ContactCreate(BaseModel):
    name: str = Field(min_length=1)
    email: Optional[str] = None
    vat_number: Optional[str] = None
    billing_address: Optional[str] = None


class ContactResponse(BaseModel):
    id: uuid.UUID
    kind: Literal["customer", "supplier"]
    name: str
    currency: Optional[str] = None
    email: Optional[str] = None
    vat_number: Optional[str] = None
    billing_address: Optional[str] = None
