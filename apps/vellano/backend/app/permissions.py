from __future__ import annotations

from typing import Optional

USERS_MANAGE = "users.manage"
SETTINGS_MUTATE = "settings.mutate"
CATALOGUE_MUTATE = "catalogue.mutate"
PO_RAISE = "po.raise"
STOCK_RECEIVE = "stock.receive"
STOCK_TRANSFER = "stock.transfer"
STOCK_ADJUST = "stock.adjust"
STOCK_COST_VIEW = "stock.cost.view"
TILL_SELL = "till.sell"
TILL_DISCOUNT = "till.discount"
SALES_RETURNS = "sales.returns"
SALES_LAYBYS = "sales.laybys"
SALES_DELIVERIES = "sales.deliveries"
SALES_CUSTOMERS = "sales.customers"
BOOKS_MUTATE = "books.mutate"
BOOKS_JOURNALS = "books.journals"
NIA_USE = "nia.use"
NIA_ADMIN = "nia.admin"

PERMISSION_CATALOG: tuple[str, ...] = (
    USERS_MANAGE,
    SETTINGS_MUTATE,
    CATALOGUE_MUTATE,
    PO_RAISE,
    STOCK_RECEIVE,
    STOCK_TRANSFER,
    STOCK_ADJUST,
    STOCK_COST_VIEW,
    TILL_SELL,
    TILL_DISCOUNT,
    SALES_RETURNS,
    SALES_LAYBYS,
    SALES_DELIVERIES,
    SALES_CUSTOMERS,
    BOOKS_MUTATE,
    BOOKS_JOURNALS,
    NIA_USE,
    NIA_ADMIN,
)

PERMISSION_CATALOG_SET: frozenset[str] = frozenset(PERMISSION_CATALOG)

SLUG_OWNER = "owner"
SLUG_BUYER = "buyer"
SLUG_WAREHOUSE = "warehouse"
SLUG_TILL = "till"
SLUG_BOOKS = "books"

ROLE_PRESET_NAMES: dict[str, str] = {
    SLUG_OWNER: "Owner",
    SLUG_BUYER: "Buyer",
    SLUG_WAREHOUSE: "Warehouse",
    SLUG_TILL: "Till",
    SLUG_BOOKS: "Books",
}

ROLE_PRESETS: dict[str, frozenset[str]] = {
    SLUG_OWNER: frozenset(PERMISSION_CATALOG),
    SLUG_BUYER: frozenset({CATALOGUE_MUTATE, PO_RAISE, STOCK_COST_VIEW, NIA_USE}),
    SLUG_WAREHOUSE: frozenset(
        {STOCK_RECEIVE, STOCK_TRANSFER, STOCK_ADJUST, SALES_RETURNS, SALES_DELIVERIES, NIA_USE}
    ),
    SLUG_TILL: frozenset(
        {
            TILL_SELL,
            TILL_DISCOUNT,
            SALES_RETURNS,
            SALES_LAYBYS,
            SALES_DELIVERIES,
            SALES_CUSTOMERS,
            NIA_USE,
        }
    ),
    SLUG_BOOKS: frozenset(
        {BOOKS_MUTATE, BOOKS_JOURNALS, SALES_CUSTOMERS, STOCK_COST_VIEW, NIA_USE}
    ),
}

SYSTEM_ROLE_SLUGS: tuple[str, ...] = (
    SLUG_OWNER,
    SLUG_BUYER,
    SLUG_WAREHOUSE,
    SLUG_TILL,
    SLUG_BOOKS,
)


def role_slug(role: object) -> str:
    value = getattr(role, "value", role)
    return str(value)


def is_known_permission(key: str) -> bool:
    return key in PERMISSION_CATALOG_SET


def validate_permission_keys(keys: list[str]) -> list[str]:
    unknown = [key for key in keys if not is_known_permission(key)]
    if unknown:
        raise ValueError(f"Unknown permission keys: {', '.join(sorted(set(unknown)))}")
    return sorted(set(keys))


def slugify_role_name(name: str, suffix: Optional[int] = None) -> str:
    chars: list[str] = []
    prev_dash = False
    for ch in name.strip().lower():
        if ch.isalnum():
            chars.append(ch)
            prev_dash = False
        elif not prev_dash:
            chars.append("-")
            prev_dash = True
    slug = "".join(chars).strip("-") or "role"
    if suffix is not None:
        slug = f"{slug}-{suffix}"
    return slug[:32]
