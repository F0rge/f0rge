"""Firstout-owned query and action capabilities, never client-provided field names."""

from __future__ import annotations

from dataclasses import dataclass

from app.models.account import Account
from app.models.customer import Customer
from app.models.location import Location
from app.models.price_list import PriceList
from app.models.proforma import Proforma
from app.models.repeating_invoice import RepeatingInvoice
from app.models.role import Role
from app.models.supplier import Supplier
from app.models.user import User
from app.models.sku import Sku
from app.permissions import (
    BOOKS_MUTATE,
    CATALOGUE_MUTATE,
    SALES_CUSTOMERS,
    STOCK_RECEIVE,
    USERS_MANAGE,
)


@dataclass(frozen=True)
class WorkspaceDefinition:
    model: type
    fields: dict[str, str]
    editable: frozenset[str]
    actions: frozenset[str]
    permission: str
    archive_field: str = "is_archived"
    read_permission: str = ""


COMMON = {"created_at": "date", "updated_at": "date"}
ARCHIVE = frozenset({"archive", "restore"})
DEFINITIONS = {
    "skus": WorkspaceDefinition(
        Sku,
        {
            **COMMON,
            "name": "text",
            "our_ref": "text",
            "our_barcode": "text",
            "category": "text",
            "preferred_supplier_id": "text",
            "preferred_supplier_name": "text",
            "is_kit": "boolean",
            "is_sellable": "boolean",
            "retail_inc_vat": "number",
        },
        frozenset(),
        ARCHIVE,
        CATALOGUE_MUTATE,
    ),
    "customers": WorkspaceDefinition(
        Customer,
        {
            **COMMON,
            "name": "text",
            "email": "text",
            "phone": "text",
            "customer_type": "text",
            "price_classification": "text",
            "price_tier": "text",
            "open_invoices_zar": "number",
            "overdue_invoices_zar": "number",
            "active_laybys_zar": "number",
            "on_hold": "boolean",
            "payment_terms_days": "number",
            "last_purchase_date": "date",
            "billing_address": "text",
        },
        frozenset(
            {
                "name",
                "email",
                "phone",
                "vat_number",
                "billing_address",
                "price_classification",
                "price_tier",
                "payment_terms_days",
                "price_list_id",
                "credit_limit",
                "on_hold",
                "on_hold_reason",
            }
        ),
        ARCHIVE | {"edit"},
        SALES_CUSTOMERS,
    ),
    "suppliers": WorkspaceDefinition(
        Supplier,
        {
            **COMMON,
            "name": "text",
            "default_currency": "text",
            "vat_number": "text",
            "address": "text",
        },
        frozenset({"name", "default_currency", "vat_number", "address"}),
        ARCHIVE | {"edit"},
        CATALOGUE_MUTATE,
    ),
    "price-lists": WorkspaceDefinition(
        PriceList,
        {**COMMON, "name": "text"},
        frozenset({"name"}),
        ARCHIVE | {"edit", "delete"},
        CATALOGUE_MUTATE,
    ),
    "locations": WorkspaceDefinition(
        Location,
        {**COMMON, "name": "text", "type": "text"},
        frozenset({"name"}),
        ARCHIVE | {"edit"},
        STOCK_RECEIVE,
    ),
    "users": WorkspaceDefinition(
        User,
        {"display_name": "text", "email": "text", "role": "text", "is_disabled": "boolean"},
        frozenset(),
        frozenset({"disable", "enable"}),
        USERS_MANAGE,
        archive_field="is_disabled",
        read_permission=USERS_MANAGE,
    ),
    "roles": WorkspaceDefinition(
        Role,
        {
            "name": "text",
            "slug": "text",
            "permissions": "text",
            "is_system": "boolean",
            "is_owner_preset": "boolean",
        },
        frozenset(),
        frozenset({"delete"}),
        USERS_MANAGE,
        archive_field="",
        read_permission=USERS_MANAGE,
    ),
    "accounts": WorkspaceDefinition(
        Account,
        {
            **COMMON,
            "code": "text",
            "name": "text",
            "type": "text",
            "tax_treatment": "text",
            "balance_zar": "number",
            "is_bank": "boolean",
        },
        frozenset({"name", "tax_treatment", "is_bank"}),
        ARCHIVE | {"edit"},
        BOOKS_MUTATE,
    ),
    "repeating-invoices": WorkspaceDefinition(
        RepeatingInvoice,
        {
            **COMMON,
            "name": "text",
            "customer_name": "text",
            "day_of_month": "number",
            "next_date": "date",
            "is_active": "boolean",
        },
        frozenset({"name", "day_of_month", "next_date"}),
        frozenset({"edit", "pause", "resume"}),
        BOOKS_MUTATE,
        archive_field="is_active",
    ),
    "proformas": WorkspaceDefinition(
        Proforma,
        {
            **COMMON,
            "invoice_number": "text",
            "supplier_name": "text",
            "currency": "text",
            "invoice_date": "date",
        },
        frozenset(),
        ARCHIVE,
        CATALOGUE_MUTATE,
    ),
}
