from __future__ import annotations

import uuid
from typing import Optional

from pydantic import BaseModel


class SupplierLeadTimeLine(BaseModel):
    supplier_id: uuid.UUID
    supplier_name: str
    n: int
    median_days: float
    median_last_3_days: float
    median_water_days: Optional[float] = None
    p90_days: Optional[float] = None


class SupplierLeadTimesReport(BaseModel):
    lines: list[SupplierLeadTimeLine]


class SkuLeadTimeLine(BaseModel):
    sku_id: uuid.UUID
    our_ref: str
    name: str
    manual_lead_time_days: Optional[int] = None
    n: int
    median_days: float
    median_last_3_days: float
    median_water_days: Optional[float] = None
    p90_days: Optional[float] = None


class SkuLeadTimesReport(BaseModel):
    lines: list[SkuLeadTimeLine]
