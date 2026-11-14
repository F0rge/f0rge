"""Validate new business without hiding the parties on existing documents."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.customer import CustomerCRUD
from app.crud.supplier import SupplierCRUD
from app.models.customer import Customer
from app.models.supplier import Supplier
from f0rge_core.exceptions import NotFoundError, ValidationError


def assert_customer_active(customer: Customer) -> None:
    if customer.is_archived:
        raise ValidationError(
            "Customer is archived. Restore this customer before creating new transactions or portal access."
        )


def assert_supplier_active(supplier: Supplier) -> None:
    if supplier.is_archived:
        raise ValidationError(
            "Supplier is archived. Restore this supplier before creating new transactions or assignments."
        )


async def require_active_customer(db: AsyncSession, customer_id: uuid.UUID) -> Customer:
    customer = await CustomerCRUD(db).get_by_id(customer_id)
    if customer is None:
        raise NotFoundError("Customer not found")
    assert_customer_active(customer)
    return customer


async def require_active_supplier(db: AsyncSession, supplier_id: uuid.UUID) -> Supplier:
    supplier = await SupplierCRUD(db).get_by_id(supplier_id)
    if supplier is None:
        raise NotFoundError("Supplier not found")
    assert_supplier_active(supplier)
    return supplier
