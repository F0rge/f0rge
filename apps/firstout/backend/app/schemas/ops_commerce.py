from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class OpsMadeToOrderOfferResponse(BaseModel):
    id: uuid.UUID
    capacity: int = Field(ge=0)
    min_lead_time_days: int = Field(ge=1)
    max_lead_time_days: int = Field(ge=1)
    expires_at: datetime


class OpsProductResponse(BaseModel):
    source_sku_id: uuid.UUID
    sku: str
    name: str
    price_minor_zar: int
    available_quantity: int
    revision: str
    observed_at: datetime
    product_group_id: Optional[uuid.UUID] = None
    product_title: Optional[str] = None
    options: dict[str, str] = Field(default_factory=dict)
    acknowledged_commitment_ids: list[str]
    made_to_order_offer: Optional[OpsMadeToOrderOfferResponse] = None


class OpsProductsResponse(BaseModel):
    company_id: uuid.UUID
    products: list[OpsProductResponse]
