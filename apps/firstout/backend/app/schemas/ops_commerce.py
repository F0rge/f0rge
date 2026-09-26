from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


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


class OpsProductsResponse(BaseModel):
    company_id: uuid.UUID
    products: list[OpsProductResponse]
