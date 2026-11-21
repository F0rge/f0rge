"""Dispatch batches through the same authoritative domain methods as single edits."""

from __future__ import annotations

import uuid

from pydantic import ValidationError as SchemaValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.role import RoleCRUD
from app.crud.user import UserCRUD
from app.models.customer import Customer
from app.models.inventory import LocationStock
from app.models.stocktake import Stocktake, StocktakeStatus
from app.permissions import SLUG_OWNER
from app.schemas.account import AccountUpdate
from app.schemas.customer_crm import CustomerCrmUpdate
from app.schemas.location import LocationUpdate
from app.schemas.price_list import PriceListUpdate
from app.schemas.repeating_invoice import RepeatingInvoiceUpdate
from app.schemas.supplier import SupplierUpdate
from app.schemas.user import UserUpdate
from app.services.accounts import AccountService
from app.services.bills import BillService
from app.services.customers_crm import CustomersCrmService
from app.services.invoices import InvoiceService
from app.services.locations import LocationService
from app.services.price_lists import PriceListService
from app.services.proformas import ProformaService
from app.services.quotes import QuotesService
from app.services.repeating_invoices import RepeatingInvoiceService
from app.services.roles import RoleService
from app.services.suppliers import SupplierService
from app.services.users import UserService
from f0rge_core.exceptions import ValidationError

PATCH_SCHEMAS = {
    "customers": CustomerCrmUpdate,
    "suppliers": SupplierUpdate,
    "price-lists": PriceListUpdate,
    "locations": LocationUpdate,
    "accounts": AccountUpdate,
    "repeating-invoices": RepeatingInvoiceUpdate,
}
NULLABLE = {
    "customers": {
        "email",
        "phone",
        "vat_number",
        "billing_address",
        "credit_limit",
        "on_hold_reason",
        "payment_terms_days",
        "price_list_id",
    },
    "suppliers": {"vat_number", "address"},
    "repeating-invoices": {"name"},
}


def validate_patch(resource: str, patch: dict, editable: frozenset[str]) -> dict:
    if set(patch) - editable:
        raise ValidationError("One or more fields cannot be bulk edited on this screen")
    if any(
        value is None and key not in NULLABLE.get(resource, set()) for key, value in patch.items()
    ):
        raise ValidationError("A required field cannot be cleared")
    try:
        validated = PATCH_SCHEMAS[resource].model_validate(patch)
    except (SchemaValidationError, KeyError) as exc:
        raise ValidationError("One or more changes contain an invalid value") from exc
    return validated.model_dump(mode="json", exclude_unset=True)


async def blocked_reason(
    db: AsyncSession, resource: str, action: str, row, count: int, patch: dict
):
    if resource == "skus":
        from app.services.sku_archive import SkuArchiveService

        return (await SkuArchiveService(db).impact(row.id, action)).reason
    if action == "edit":
        if getattr(row, "is_archived", False):
            return "Restore this record before editing it"
        if (
            count > 1
            and "name" in patch
            and resource in {"customers", "suppliers", "price-lists", "locations"}
        ):
            return "Names must be changed individually to preserve unique record identities"
    if resource == "roles":
        return await RoleService(db).deletion_block_reason(row)
    if resource == "invoices" and row.source == "imported":
        return "Imported invoices are read-only history"
    if resource == "quotes" and row.is_converted:
        return "Converted quotes are kept; duplicate one to quote again"
    if resource == "users" and action == "disable":
        owner_slugs = await RoleCRUD(db).list_owner_slugs()
        if row.role == SLUG_OWNER or row.role in owner_slugs:
            return "Owner access must be managed individually"
    if resource == "users" and action == "enable":
        identity = await UserCRUD(db).get_by_id(row.id)
        if identity is not None and identity.is_disabled:
            return "Global identity access must be managed separately"
    if resource == "accounts" and action == "archive" and row.is_system:
        return "System posting accounts are protected"
    if resource == "price-lists" and action == "delete":
        assigned = await db.scalar(
            select(func.count()).select_from(Customer).where(Customer.price_list_id == row.id)
        )
        if assigned:
            return "This price list is assigned to customers; archive it instead"
    if resource == "locations" and action == "archive":
        has_stock = await db.scalar(
            select(LocationStock.id)
            .where(LocationStock.location_id == row.id, LocationStock.on_hand != 0)
            .limit(1)
        )
        if has_stock:
            return "Move the remaining stock before archiving this location"
        counting = await db.scalar(
            select(Stocktake.id)
            .where(Stocktake.location_id == row.id, Stocktake.status == StocktakeStatus.IN_PROGRESS)
            .limit(1)
        )
        if counting:
            return "Complete or cancel the active stocktake first"
    return None


async def apply_action(
    db: AsyncSession,
    resource: str,
    action: str,
    record_id: uuid.UUID,
    patch: dict,
    actor: uuid.UUID,
) -> None:
    if resource == "skus":
        from app.services.sku_archive import SkuArchiveService

        await SkuArchiveService(db).set_archived(record_id, action == "archive", actor)
    elif resource == "customers":
        service = CustomersCrmService(db)
        if action == "edit":
            await service.update(record_id, CustomerCrmUpdate.model_validate(patch), actor)
        else:
            await service.set_archived(record_id, action == "archive")
    elif resource == "suppliers":
        service = SupplierService(db)
        if action == "edit":
            await service.update(record_id, SupplierUpdate.model_validate(patch))
        else:
            await service.set_archived(record_id, action == "archive")
    elif resource == "price-lists":
        service = PriceListService(db)
        if action == "edit":
            await service.update(record_id, PriceListUpdate.model_validate(patch))
        elif action == "delete":
            await service.delete(record_id)
        else:
            await service.set_archived(record_id, action == "archive")
    elif resource == "proformas":
        await ProformaService(db).set_archived(record_id, action == "archive")
    elif resource == "quotes":
        await QuotesService(db).delete(record_id)
    elif resource == "bills":
        await BillService(db).set_archived(record_id, action == "archive", actor)
    elif resource == "invoices":
        await InvoiceService(db).set_archived(record_id, action == "archive", actor)
    elif resource == "locations":
        data = patch if action == "edit" else {"is_archived": action == "archive"}
        await LocationService(db).update(record_id, LocationUpdate.model_validate(data))
    elif resource == "accounts":
        data = patch if action == "edit" else {"is_archived": action == "archive"}
        await AccountService(db).update(record_id, AccountUpdate.model_validate(data))
    elif resource == "repeating-invoices":
        data = patch if action == "edit" else {"is_active": action == "resume"}
        await RepeatingInvoiceService(db).update(
            record_id, RepeatingInvoiceUpdate.model_validate(data)
        )
    elif resource == "users":
        await UserService(db).update(record_id, UserUpdate(is_disabled=action == "disable"))
    else:
        await RoleService(db).delete(record_id)
