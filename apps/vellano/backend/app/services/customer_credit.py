from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.customer import CustomerCRUD, CustomerInvoiceAgg
from app.exceptions import ForbiddenError
from app.models.customer import Customer
from app.permissions import PO_RAISE, USERS_MANAGE
from app.services.permissions import PermissionService
from app.services.till_seed import WALK_IN_CUSTOMER_NAME
from f0rge_core.exceptions import ConflictError, ValidationError

CREDIT_OVERRIDE_KEYS = (USERS_MANAGE, PO_RAISE)
CUSTOMER_ON_HOLD = "Customer is on hold"
CUSTOMER_EXCEEDS_CREDIT_LIMIT = "Customer exceeds credit limit"


class CustomerCreditService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = CustomerCRUD(db)
        self.permissions = PermissionService(db)

    def is_walk_in(self, customer: Customer) -> bool:
        return customer.name == WALK_IN_CUSTOMER_NAME

    async def authorize_override(
        self,
        *,
        credit_override: bool,
        credit_override_reason: Optional[str],
        user_id: Optional[uuid.UUID],
    ) -> Optional[str]:
        if not credit_override:
            return None
        reason = (credit_override_reason or "").strip()
        if not reason:
            raise ValidationError("credit_override_reason is required")
        if user_id is None or not await self.permissions.has_any(user_id, CREDIT_OVERRIDE_KEYS):
            raise ForbiddenError("Credit override permission required")
        return f"credit override: {reason}"

    async def assert_not_held(self, customer: Customer, *, credit_override: bool) -> None:
        if self.is_walk_in(customer):
            return
        if customer.on_hold and not credit_override:
            raise ConflictError(CUSTOMER_ON_HOLD)

    async def assert_within_limit(
        self,
        customer: Customer,
        sale_total: Decimal,
        *,
        credit_override: bool,
    ) -> None:
        if self.is_walk_in(customer) or credit_override or customer.credit_limit is None:
            return
        aggs = await self.crud.invoice_aggregates_for_customers(
            [customer.id], datetime.date.today()
        )
        open_zar = aggs.get(customer.id, CustomerInvoiceAgg()).open_zar
        if open_zar + sale_total > customer.credit_limit:
            raise ConflictError(CUSTOMER_EXCEEDS_CREDIT_LIMIT)

    async def assert_allowed(
        self,
        customer: Customer,
        sale_total: Decimal,
        *,
        credit_override: bool,
        credit_override_reason: Optional[str],
        user_id: Optional[uuid.UUID],
    ) -> Optional[str]:
        if self.is_walk_in(customer):
            return None
        note = await self.authorize_override(
            credit_override=credit_override,
            credit_override_reason=credit_override_reason,
            user_id=user_id,
        )
        await self.assert_not_held(customer, credit_override=credit_override)
        await self.assert_within_limit(customer, sale_total, credit_override=credit_override)
        return note
