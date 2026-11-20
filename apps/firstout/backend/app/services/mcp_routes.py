"""MCP actions generated from the staff API.

Each action runs the real route as the token owner, so the route's own permission
dependency, validation and business logic apply. A route is offered only when its API tag
appears in `TABS`; everything else is left out and must be named in an exclusion table.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterator
from typing import Any

from fastapi import FastAPI, params
from fastapi.datastructures import DefaultPlaceholder
from fastapi.dependencies.models import Dependant
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute, RouteContext, iter_route_contexts
from pydantic import BaseModel, create_model

from app.middleware.auth import get_current_user_id
from app.services.mcp_action_types import Action, Arguments, RouteCall

# API tag -> sidebar tab. A tag whose routes belong to several tabs maps the first path
# segment after /api/v1 instead. A tag missing here is never offered through MCP.
TABS: dict[str, str | dict[str, str]] = {
    "accounts": "Books / Chart of accounts",
    "adjustments": "Stock / Adjustments",
    "audit": "Admin / Audit log",
    "bank-imports": "Books / Bank reconciliation",
    "bank-rules": "Books / Bank reconciliation",
    "bills": "Books / Bills",
    "books-events": "Books / Journals",
    "books-periods": "Books / Books periods",
    "category-maps": "Books / Chart of accounts",
    "cost-audit": "Catalogue / Catalogue",
    "credit-notes": "Books / Credit notes",
    "customers": "Sales / Customers",
    "deliveries": "Sales / Deliveries",
    "document-intake": "Catalogue / Proformas",
    "home": "Home",
    "imports": "Stock / Import",
    "inventory": "Stock / Stock by bin",
    "invoices": "Books / Invoices",
    "journal-imports": "Books / Journals",
    "journals": "Books / Journals",
    "laybys": "Sales / Laybys",
    "locations": "Catalogue / Locations",
    "payments": "Books / Payments",
    "picks": "Warehouse / Picks",
    "price-lists": "Catalogue / Price lists",
    "proformas": "Catalogue / Proformas",
    "purchase-orders": "Warehouse / Purchase orders",
    "quotes": "Sales / Quotes",
    "receive": "Warehouse / Receive",
    "records": {
        "customers": "Sales / Customers",
        "history": "Sales / History",
        "stock": "Stock / Stock by bin",
        "supplier-prices": "Catalogue / Suppliers",
        "suppliers": "Catalogue / Suppliers",
    },
    "reorder": "Stock / Reorder",
    "repeating-invoices": "Books / Repeating invoices",
    "reports": "Books / Reports",
    "returns": "Sales / Returns",
    "sales-orders": "Sales / Orders",
    "search": "Home",
    "settings": "Admin / Settings directory",
    "skus": "Catalogue / Catalogue",
    "stocktakes": "Stock / Stocktakes",
    "suppliers": "Catalogue / Suppliers",
    "till": "Till",
    "transfers": "Warehouse / Transfers",
    "vat201": "Books / VAT201",
}

# API tag -> why MCP leaves it out.
EXCLUDED_TAGS: dict[str, str] = {
    "auth": "identity",
    "mcp-tokens": "identity",
    "organisations": "identity",
    "profile": "identity",
    # Its bulk actions also edit, disable and delete users and roles.
    "record-workspaces": "identity",
    "roles": "identity",
    "tenant-signup": "identity",
    "users": "identity",
    "customer-portal": "non-staff",
    "health": "non-staff",
    "ops-commerce": "non-staff",
    "storefront-orders": "non-staff",
    "webhooks": "non-staff",
}

# Path prefix -> why MCP leaves it out, for routes inside a tag that is otherwise offered.
EXCLUDED_PATHS: dict[str, str] = {
    # Customer portal logins, invitations and access grants.
    "/api/v1/customers/{customer_id}/portal-": "identity",
}

UNCLASSIFIED = "unclassified"
_PREFIX = "/api/v1/"
_MAX_NAME = 80


def api_routes(app: FastAPI) -> Iterator[RouteContext]:
    # Routers are included lazily, so `app.routes` does not hold the API routes themselves.
    return (
        route
        for route in iter_route_contexts(app.routes)
        if isinstance(route.original_route, APIRoute)
    )


def _tree(dependant: Dependant) -> Iterator[Dependant]:
    for child in dependant.dependencies:
        yield child
        yield from _tree(child)


def _fields(route: RouteContext, kind: str) -> list[Any]:
    """The route's own and its dependencies' parameters of one kind, once per name."""
    by_name = {
        field.name: field
        for dependant in (route.dependant, *_tree(route.dependant))
        for field in getattr(dependant, kind)
    }
    return list(by_name.values())


def _tab(route: RouteContext) -> str | None:
    tab = TABS.get(route.tags[0]) if len(route.tags) == 1 else None
    if isinstance(tab, dict):
        return tab.get(route.path.removeprefix(_PREFIX).split("/")[0])
    return tab


def exclusion(route: RouteContext) -> str | None:
    """Why MCP leaves this route out, or None when it is offered."""
    for tag in route.tags:
        if tag in EXCLUDED_TAGS:
            return EXCLUDED_TAGS[tag]
    for prefix, reason in EXCLUDED_PATHS.items():
        if route.path.startswith(prefix):
            return reason
    if _tab(route) is None or not route.path.startswith(_PREFIX):
        return UNCLASSIFIED
    if all(child.call is not get_current_user_id for child in _tree(route.dependant)):
        return "non-staff"
    if any(
        isinstance(field.field_info, (params.Form, params.File))
        for field in _fields(route, "body_params")
    ):
        return "files"
    response_class = route.response_class
    if isinstance(response_class, DefaultPlaceholder):
        response_class = response_class.value
    # PDF, CSV and file routes return a raw response and declare no JSON model.
    if not issubclass(response_class, JSONResponse) or (
        route.response_model is None and route.status_code != 204
    ):
        return "files"
    return None


def _permissions(route: RouteContext) -> tuple[str, ...]:
    """The keys of the route's permission dependency. Empty means any active staff member."""
    guards = {
        id(child.call): child.call.permissions
        for child in _tree(route.dependant)
        if hasattr(child.call, "permissions")
    }
    if any(not keys for keys in guards.values()):
        # A permission dependency without keys denies everyone, while an action without
        # permissions is open to all staff. Never translate one into the other.
        raise TypeError(f"MCP cannot represent the empty permission check on {route.path}")
    if len(guards) > 1:
        # ponytail: Action.permissions means "any of", which cannot express two guards that
        # must both pass. No route has two; give Action an all-of form when one does.
        raise TypeError(f"MCP cannot represent the two permission checks on {route.path}")
    return tuple(next(iter(guards.values()), ()))


async def _runs_through_the_api(db: Any, token: Any, args: Any) -> dict:
    raise RuntimeError("A route action runs its API route, not a handler")


def _action(app: FastAPI, route: RouteContext, name: str) -> Action:
    (method,) = route.methods
    path, query, body = (
        _fields(route, kind) for kind in ("path_params", "query_params", "body_params")
    )
    extra = [
        field.name
        for field in (*_fields(route, "header_params"), *_fields(route, "cookie_params"))
        if field.name != "authorization"
    ]
    fields: dict[str, Any] = {
        field.name: (field.field_info.annotation, field.field_info) for field in (*path, *query)
    }
    for field in body:
        fields["body"] = (field.field_info.annotation, field.field_info)
    if (
        extra
        or len(body) > 1
        or len(name) > _MAX_NAME
        or len(fields) != len(path) + len(query) + len(body)
        or any(getattr(field.field_info, "embed", None) for field in body)
        # A parameter model would be sent as one value instead of its separate fields.
        or any(
            isinstance(field.field_info.annotation, type)
            and issubclass(field.field_info.annotation, BaseModel)
            for field in query
        )
    ):
        raise TypeError(f"MCP cannot derive an action for {method} {route.path}")
    title = name.replace("_", " ").capitalize()
    summary = route.summary or (route.description or "").strip().split("\n")[0]
    return Action(
        name=name,
        tab=_tab(route),
        description=f"{(summary or title).rstrip('.')}. {method} {route.path}",
        arguments=create_model(
            name.title().replace("_", "") + "RouteArguments", __base__=Arguments, **fields
        ),
        permissions=_permissions(route),
        handler=_runs_through_the_api,
        effect="read" if method == "GET" else "write",
        route=RouteCall(
            app=app,
            method=method,
            path=route.path,
            path_params=tuple(field.name for field in path),
            query_params=tuple((field.name, field.alias) for field in query),
        ),
    )


def route_actions(app: FastAPI, reserved: frozenset[str]) -> tuple[Action, ...]:
    """One action per offered route, named after its endpoint function.

    A function name already used by a hand-written action, or shared by two offered routes,
    is prefixed with the route's API tag. Names are saved with write receipts, so they must
    not depend on anything that changes between deploys.
    """
    offered = [route for route in api_routes(app) if exclusion(route) is None]
    seen = Counter(route.name for route in offered)
    return tuple(
        _action(
            app,
            route,
            route.name
            if seen[route.name] == 1 and route.name not in reserved
            else f"{route.tags[0].replace('-', '_')}_{route.name}",
        )
        for route in offered
    )
