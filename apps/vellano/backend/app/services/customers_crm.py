from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.customer import CustomerCRUD, CustomerInvoiceAgg, CustomerLaybyAgg
from app.exceptions import ForbiddenError
from app.models.customer import Customer
from app.permissions import SALES_CUSTOMERS
from app.schemas.customer_crm import (
    CustomerCrmCreate,
    CustomerCrmResponse,
    CustomerCrmUpdate,
)
from app.services.customer_credit import CREDIT_OVERRIDE_KEYS
from app.services.permissions import PermissionService
from f0rge_core.exceptions import ConflictError, NotFoundError, ValidationError
from f0rge_db.crud import unit_of_work

CREDIT_PATCH_FIELDS = frozenset({"credit_limit", "on_hold", "on_hold_reason"})
PROFILE_PATCH_FIELDS = frozenset(
    {
        "name",
        "email",
        "phone",
        "vat_number",
        "billing_address",
        "customer_type",
        "price_tier",
    }
)


class CustomersCrmService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = CustomerCRUD(db)
        self.permissions = PermissionService(db)

    async def list(
        self,
        overdue: Optional[bool] = None,
        active_layby: Optional[bool] = None,
        on_hold: Optional[bool] = None,
    ) -> list[CustomerCrmResponse]:
        customers = await self.crud.list_all()
        responses = await self._to_responses(customers)
        if overdue is not None:
            responses = [row for row in responses if (row.overdue_invoices_count > 0) is overdue]
        if active_layby is not None:
            responses = [row for row in responses if (row.active_laybys_count > 0) is active_layby]
        if on_hold is not None:
            responses = [row for row in responses if row.on_hold is on_hold]
        return responses

    async def get(self, customer_id: uuid.UUID) -> CustomerCrmResponse:
        customer = await self.crud.get_by_id(customer_id)
        if customer is None:
            raise NotFoundError("Customer not found")
        responses = await self._to_responses([customer])
        return responses[0]

    async def create(self, data: CustomerCrmCreate) -> CustomerCrmResponse:
        self._validate_customer_type(data.customer_type)
        customer = Customer(
            name=data.name,
            email=data.email,
            phone=data.phone,
            vat_number=data.vat_number,
            billing_address=data.billing_address,
            customer_type=data.customer_type,
            price_tier=data.price_tier,
        )
        async with unit_of_work(self.db):
            await self.crud.add_and_flush(customer)
            try:
                await self.crud.commit_refresh(customer)
            except IntegrityError as exc:
                raise ConflictError("Customer could not be created") from exc

        return await self.get(customer.id)

    async def update(
        self,
        customer_id: uuid.UUID,
        data: CustomerCrmUpdate,
        user_id: uuid.UUID,
    ) -> CustomerCrmResponse:
        customer = await self.crud.get_by_id(customer_id)
        if customer is None:
            raise NotFoundError("Customer not found")

        fields_set = data.model_fields_set
        await self._assert_patch_permissions(user_id, fields_set)
        if "name" in fields_set and data.name is not None:
            customer.name = data.name
        if "email" in fields_set:
            customer.email = data.email
        if "phone" in fields_set:
            customer.phone = data.phone
        if "vat_number" in fields_set:
            customer.vat_number = data.vat_number
        if "billing_address" in fields_set:
            customer.billing_address = data.billing_address
        if "customer_type" in fields_set:
            if data.customer_type is None:
                raise ValidationError("customer_type cannot be null")
            self._validate_customer_type(data.customer_type)
            customer.customer_type = data.customer_type
        if "price_tier" in fields_set:
            if data.price_tier is None:
                raise ValidationError("price_tier cannot be null")
            customer.price_tier = data.price_tier
        if "credit_limit" in fields_set:
            customer.credit_limit = data.credit_limit
        if "on_hold" in fields_set:
            if data.on_hold is None:
                raise ValidationError("on_hold cannot be null")
            customer.on_hold = data.on_hold
        if "on_hold_reason" in fields_set:
            customer.on_hold_reason = data.on_hold_reason

        async with unit_of_work(self.db):
            try:
                await self.crud.commit_refresh(customer)
            except IntegrityError as exc:
                raise ConflictError("Customer could not be updated") from exc

        return await self.get(customer.id)

    async def _to_responses(self, customers: list[Customer]) -> list[CustomerCrmResponse]:
        if not customers:
            return []

        today = datetime.date.today()
        customer_ids = [customer.id for customer in customers]
        invoice_aggs = await self.crud.invoice_aggregates_for_customers(customer_ids, today)
        layby_aggs = await self.crud.layby_aggregates_for_customers(customer_ids)

        return [
            self._to_response(
                customer,
                invoice_aggs.get(customer.id, CustomerInvoiceAgg()),
                layby_aggs.get(customer.id, CustomerLaybyAgg()),
            )
            for customer in customers
        ]

    def _to_response(
        self,
        customer: Customer,
        invoice_agg: CustomerInvoiceAgg,
        layby_agg: CustomerLaybyAgg,
    ) -> CustomerCrmResponse:
        return CustomerCrmResponse(
            id=customer.id,
            name=customer.name,
            email=customer.email,
            phone=customer.phone,
            vat_number=customer.vat_number,
            billing_address=customer.billing_address,
            customer_type=customer.customer_type,
            price_tier=customer.price_tier,
            credit_limit=(
                customer.credit_limit.quantize(Decimal("0.01"))
                if customer.credit_limit is not None
                else None
            ),
            on_hold=customer.on_hold,
            on_hold_reason=customer.on_hold_reason,
            open_invoices_count=invoice_agg.open_count,
            open_invoices_zar=invoice_agg.open_zar.quantize(Decimal("0.01")),
            overdue_invoices_count=invoice_agg.overdue_count,
            overdue_invoices_zar=invoice_agg.overdue_zar.quantize(Decimal("0.01")),
            last_purchase_date=invoice_agg.last_purchase_date,
            active_laybys_count=layby_agg.active_count,
            active_laybys_zar=layby_agg.active_zar.quantize(Decimal("0.01")),
            created_at=customer.created_at,
            updated_at=customer.updated_at,
        )

    async def _assert_patch_permissions(self, user_id: uuid.UUID, fields_set: set[str]) -> None:
        if fields_set & PROFILE_PATCH_FIELDS:
            if not await self.permissions.has_permission(user_id, SALES_CUSTOMERS):
                raise ForbiddenError("Customer profile permission required")
        if fields_set & CREDIT_PATCH_FIELDS:
            if not await self.permissions.has_any(user_id, CREDIT_OVERRIDE_KEYS):
                raise ForbiddenError("Credit fields require additional permission")

    def _validate_customer_type(self, customer_type: str) -> None:
        if customer_type not in ("retail", "trade"):
            raise ValidationError("customer_type must be retail or trade")
