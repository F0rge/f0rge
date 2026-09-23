from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class OpsProductResponse(BaseModel):
    source_sku_id: uuid.UUID
    sku: str
    name: str
    price_minor_zar: int
    available_quantity: int
    revision: str
    observed_at: datetime


class OpsProductsResponse(BaseModel):
    company_id: uuid.UUID
    products: list[OpsProductResponse]
