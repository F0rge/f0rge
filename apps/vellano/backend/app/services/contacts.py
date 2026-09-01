from __future__ import annotations

import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.customer import CustomerCRUD
from app.crud.supplier import SupplierCRUD
from app.models.customer import Customer
from app.schemas.contact import ContactCreate, ContactResponse
from f0rge_core.exceptions import ConflictError, NotFoundError
from f0rge_db.crud import unit_of_work


class ContactService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.customer_crud = CustomerCRUD(db)
        self.supplier_crud = SupplierCRUD(db)

    async def list(self) -> list[ContactResponse]:
        customers = await self.customer_crud.list_all()
        suppliers = await self.supplier_crud.list_all()
        contacts: list[ContactResponse] = []
        for customer in customers:
            contacts.append(
                ContactResponse(
                    id=customer.id,
                    kind="customer",
                    name=customer.name,
                    currency=None,
                    email=customer.email,
                    vat_number=customer.vat_number,
                    billing_address=customer.billing_address,
                )
            )
        for supplier in suppliers:
            contacts.append(
                ContactResponse(
                    id=supplier.id,
                    kind="supplier",
                    name=supplier.name,
                    currency=supplier.default_currency,
                )
            )
        contacts.sort(key=lambda item: (item.kind, item.name.lower()))
        return contacts

    async def create_customer(self, data: ContactCreate) -> ContactResponse:
        customer = Customer(
            name=data.name,
            email=data.email,
            vat_number=data.vat_number,
            billing_address=data.billing_address,
        )
        async with unit_of_work(self.db):
            await self.customer_crud.add_and_flush(customer)
            try:
                await self.customer_crud.commit_refresh(customer)
            except IntegrityError as exc:
                raise ConflictError("Customer could not be created") from exc

        return ContactResponse(
            id=customer.id,
            kind="customer",
            name=customer.name,
            currency=None,
            email=customer.email,
            vat_number=customer.vat_number,
            billing_address=customer.billing_address,
        )

    async def get_customer(self, customer_id: uuid.UUID) -> Customer:
        customer = await self.customer_crud.get_by_id(customer_id)
        if customer is None:
            raise NotFoundError("Customer not found")
        return customer
