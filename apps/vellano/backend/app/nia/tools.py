from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Any, Optional, Union

from pydantic_ai import ApprovalRequired, RunContext
from sqlalchemy import and_, select

from app.crud.location import LocationCRUD
from app.crud.sku import SkuCRUD
from app.models.tax_invoice import TaxInvoice
from app.nia.agent import NiaDeps, nia_agent
from app.permissions import NIA_USE, STOCK_TRANSFER
from app.schemas.transfer import TransferCreate, TransferLineCreate
from app.services.inventory import InventoryService
from app.services.search import SearchService
from app.services.transfers import TransferService

ALLOWED_NAV_PATHS: frozenset[str] = frozenset(
    {
        "/",
        "/locations",
        "/suppliers",
        "/proformas",
        "/catalogue",
        "/stock",
        "/stocktakes",
        "/adjustments",
        "/import",
        "/reorder",
        "/purchase-orders",
        "/transit",
        "/receive",
        "/wms",
        "/transfers",
        "/picks",
        "/deliveries",
        "/till",
        "/laybys",
        "/returns",
        "/customers",
        "/ledger",
        "/journals",
        "/contacts",
        "/invoices",
        "/repeating-invoices",
        "/credit-notes",
        "/bills",
        "/payments",
        "/bank-reconciliation",
        "/reports",
        "/vat201",
        "/users",
        "/roles",
        "/profile",
        "/settings",
        "/canvas",
    }
)

PROPOSE_TRANSFER_TOOL = "propose_transfer"


def _has_permission(deps: NiaDeps, key: str) -> bool:
    return key in deps.permissions


def _require_nia_use(deps: NiaDeps) -> Optional[str]:
    if not _has_permission(deps, NIA_USE):
        return "You do not have permission to use Nia tools."
    return None


def _set_structured_payload(ctx: RunContext[NiaDeps], payload: dict[str, Any]) -> None:
    ctx.deps.last_structured_payload = payload


async def _resolve_sku_id(db, sku_ref: str) -> Optional[uuid.UUID]:
    ref = sku_ref.strip()
    sku_crud = SkuCRUD(db)
    try:
        sku_id = uuid.UUID(ref)
    except ValueError:
        sku = await sku_crud.get_by_our_ref(ref)
        return sku.id if sku is not None else None
    sku = await sku_crud.get_by_id(sku_id)
    return sku.id if sku is not None else None


async def _resolve_location_id(db, location_name: str) -> Optional[uuid.UUID]:
    location = await LocationCRUD(db).get_active_by_name_insensitive(location_name.strip())
    return location.id if location is not None else None


@nia_agent.tool
async def navigate(ctx: RunContext[NiaDeps], path: str) -> Union[dict[str, str], str]:
    """Open an in-app page by path. Use only known Vellano routes."""
    denied = _require_nia_use(ctx.deps)
    if denied:
        return denied

    normalized = path.strip()
    if not normalized.startswith("/"):
        normalized = f"/{normalized}"

    if normalized not in ALLOWED_NAV_PATHS:
        return f"Navigation denied: unknown route {normalized}"

    payload = {"kind": "opened_page", "path": normalized}
    _set_structured_payload(ctx, payload)
    return payload


@nia_agent.tool
async def search(ctx: RunContext[NiaDeps], q: str) -> Union[dict[str, Any], str]:
    """Search SKUs, purchase orders, and invoices by reference or name."""
    denied = _require_nia_use(ctx.deps)
    if denied:
        return denied

    try:
        result = await SearchService(ctx.deps.db).search(q)
    except Exception as exc:
        return f"Search failed: {exc}"
    return result.model_dump(mode="json")


@nia_agent.tool
async def list_overdue_invoices(ctx: RunContext[NiaDeps]) -> Union[list[dict[str, Any]], str]:
    """List unpaid invoices past 30-day terms (issue_date + 30)."""
    denied = _require_nia_use(ctx.deps)
    if denied:
        return denied

    today = datetime.date.today()
    overdue_cutoff = today - datetime.timedelta(days=30)
    balance = TaxInvoice.total_inc_vat - TaxInvoice.amount_paid
    stmt = (
        select(TaxInvoice)
        .where(
            and_(
                balance > 0,
                TaxInvoice.issue_date <= overdue_cutoff,
            )
        )
        .order_by(TaxInvoice.issue_date, TaxInvoice.invoice_number)
    )
    rows = (await ctx.deps.db.execute(stmt)).scalars().all()
    invoices = [
        {
            "id": str(inv.id),
            "invoice_number": inv.invoice_number,
            "remaining_zar": str((inv.total_inc_vat - inv.amount_paid).quantize(Decimal("0.01"))),
        }
        for inv in rows
    ]
    if invoices:
        _set_structured_payload(ctx, {"kind": "overdue_invoices", "invoices": invoices})
    return invoices


@nia_agent.tool
async def get_stock_on_hand(
    ctx: RunContext[NiaDeps],
    sku: str,
    location: str,
) -> Union[dict[str, object], str]:
    """Return on-hand quantity for a SKU at a location (by our_ref or SKU id and location name)."""
    denied = _require_nia_use(ctx.deps)
    if denied:
        return denied

    payload = await InventoryService(ctx.deps.db).get_at_location(
        sku,
        location,
        ctx.deps.user_id,
    )
    if "error" in payload:
        return str(payload["error"])
    return payload


@nia_agent.tool
async def propose_transfer(
    ctx: RunContext[NiaDeps],
    from_location: str,
    to_location: str,
    sku: str,
    qty: int,
) -> Union[dict[str, Any], str]:
    """Propose an internal stock transfer (draft only; requires approval when permitted)."""
    if not _has_permission(ctx.deps, STOCK_TRANSFER):
        return (
            "Transfer denied: your role cannot create stock transfers. "
            "Ask warehouse or an owner to move stock."
        )

    if qty <= 0:
        return "Transfer denied: quantity must be greater than zero."

    from_id = await _resolve_location_id(ctx.deps.db, from_location)
    to_id = await _resolve_location_id(ctx.deps.db, to_location)
    if from_id is None:
        return f"Transfer denied: source location not found: {from_location}"
    if to_id is None:
        return f"Transfer denied: destination location not found: {to_location}"
    if from_id == to_id:
        return "Transfer denied: source and destination must differ."

    sku_id = await _resolve_sku_id(ctx.deps.db, sku)
    if sku_id is None:
        return f"Transfer denied: SKU not found: {sku}"

    if not ctx.tool_call_approved:
        raise ApprovalRequired(
            metadata={
                "kind": "needs_ok",
                "title": "Approve stock transfer",
                "body": (
                    f"Create draft transfer of {qty} × {sku.strip()} "
                    f"from {from_location.strip()} to {to_location.strip()}?"
                ),
            }
        )

    transfer = await TransferService(ctx.deps.db).create(
        TransferCreate(
            from_location_id=from_id,
            to_location_id=to_id,
            lines=[TransferLineCreate(sku_id=sku_id, qty=qty)],
        ),
        ctx.deps.user_id,
    )
    return {
        "kind": "transfer_draft",
        "transfer_id": str(transfer.id),
        "transfer_number": transfer.transfer_number,
        "status": transfer.status.value,
    }
