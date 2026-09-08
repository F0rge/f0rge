from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class UnitCostAuditResponse(BaseModel):
    id: uuid.UUID
    sku_id: uuid.UUID
    location_id: Optional[uuid.UUID]
    location_name: Optional[str]
    po_id: Optional[uuid.UUID]
    old_cost_zar: Optional[Decimal]
    new_cost_zar: Decimal
    changed_by_user_id: uuid.UUID
    changed_by_email: str
    changed_by_display_name: Optional[str]
    source: str
    note: Optional[str]
    created_at: datetime


class UnitCostCorrectionRequest(BaseModel):
    location_id: uuid.UUID
    unit_cost_zar: Decimal
