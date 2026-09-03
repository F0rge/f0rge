from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Any, Optional, Union

from pydantic_ai import ApprovalRequired, RunContext, ToolReturn
from sqlalchemy import and_, select
from sqlalchemy.orm import selectinload

from app.crud.location import LocationCRUD
from app.crud.sku import SkuCRUD
from app.models.tax_invoice import TaxInvoice
from app.nia.agent import NiaDeps, nia_agent
from app.nia.milestones import milestone_tool_return
from app.nia.canvas import (
    add_canvas_component as merge_add_canvas_component,
    build_aged_ar_canvas_spec,
    build_dining_vs_sofas_canvas_spec,
    build_overdue_invoices_canvas_spec,
    build_sales_by_sku_canvas_spec,
    build_stock_on_hand_canvas_spec,
    canvas_cleared_payload,
    empty_canvas_spec,
    merge_canvas_mode,
    remove_canvas_component as drop_canvas_component,
    set_canvas_spec,
    set_canvas_title as apply_canvas_title,
)
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
_INVOICE_DETAIL_PREFIX = "/invoices/"
_OVERDUE_TERMS_DAYS = 30


def _is_allowed_nav_path(normalized: str) -> bool:
    """Exact allowlisted routes, plus invoice detail `/invoices/{uuid}`."""
    if normalized in ALLOWED_NAV_PATHS:
        return True
    if not normalized.startswith(_INVOICE_DETAIL_PREFIX):
        return False
    suffix = normalized[len(_INVOICE_DETAIL_PREFIX) :]
    if not suffix or "/" in suffix:
        return False
    try:
        uuid.UUID(suffix)
    except ValueError:
        return False
    return True


def _has_permission(deps: NiaDeps, key: str) -> bool:
    return key in deps.permissions


def _require_nia_use(deps: NiaDeps) -> Optional[str]:
    if not _has_permission(deps, NIA_USE):
        return "You do not have permission to use Nia tools."
    return None


def _set_structured_payload(ctx: RunContext[NiaDeps], payload: dict[str, Any]) -> None:
    ctx.deps.last_structured_payload = payload


def _current_canvas(deps: NiaDeps) -> dict[str, Any]:
    spec = deps.canvas_spec
    if isinstance(spec, dict) and spec.get("kind") == "canvas_spec":
        return spec
    return empty_canvas_spec()


def _publish_canvas_spec(ctx: RunContext[NiaDeps], spec: dict[str, Any]) -> dict[str, Any]:
    ctx.deps.canvas_spec = spec
    ctx.deps.last_canvas_payload = spec
    _set_structured_payload(ctx, spec)
    return spec


def _apply_chart_spec(
    ctx: RunContext[NiaDeps],
    incoming: dict[str, Any],
    mode: Optional[str],
) -> dict[str, Any]:
    merged = merge_canvas_mode(_current_canvas(ctx.deps), incoming, mode or "replace")
    return _publish_canvas_spec(ctx, merged)


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
    """Open an in-app page by path. Use only known Vellano routes.

    Opening a page does not replace answering a recommendation question.
    """
    denied = _require_nia_use(ctx.deps)
    if denied:
        return denied

    normalized = path.strip()
    if not normalized.startswith("/"):
        normalized = f"/{normalized}"

    if not _is_allowed_nav_path(normalized):
        return f"Navigation denied: unknown route {normalized}"

    payload = {"kind": "opened_page", "path": normalized}
    _set_structured_payload(ctx, payload)
    return payload


@nia_agent.tool
async def report_milestone(ctx: RunContext[NiaDeps], label: str) -> ToolReturn:
    """Report a short progress label to the user while you work.

    Call this between steps so the dock shows progress before the final answer.
    Keep the label plain words, no emojis.
    """
    denied = _require_nia_use(ctx.deps)
    if denied:
        return ToolReturn(return_value=denied)
    return milestone_tool_return(label)


@nia_agent.tool
async def search(ctx: RunContext[NiaDeps], q: str) -> Union[dict[str, Any], str]:
    """Search SKUs, purchase orders, and invoices by reference or name.

    Summarise the answer in the assistant message first, then optionally open a page.
    """
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
    """List unpaid invoices past 30-day terms (issue_date + 30).

    Summarise the requested invoice facts neutrally. Recommend chasing only when
    the current user message explicitly asks for that recommendation.
    """
    denied = _require_nia_use(ctx.deps)
    if denied:
        return denied

    today = datetime.date.today()
    overdue_cutoff = today - datetime.timedelta(days=_OVERDUE_TERMS_DAYS)
    balance = TaxInvoice.total_inc_vat - TaxInvoice.amount_paid
    stmt = (
        select(TaxInvoice)
        .options(selectinload(TaxInvoice.customer))
        .where(
            and_(
                balance > 0,
                TaxInvoice.issue_date <= overdue_cutoff,
            )
        )
        .order_by(TaxInvoice.issue_date, TaxInvoice.invoice_number)
    )
    rows = (await ctx.deps.db.execute(stmt)).scalars().all()
    invoices = []
    for inv in rows:
        due_date = inv.issue_date + datetime.timedelta(days=_OVERDUE_TERMS_DAYS)
        invoices.append(
            {
                "id": str(inv.id),
                "invoice_number": inv.invoice_number,
                "customer_name": inv.customer.name,
                "issue_date": inv.issue_date.isoformat(),
                "days_overdue": (today - due_date).days,
                "terms_days": _OVERDUE_TERMS_DAYS,
                "remaining_zar": str(
                    (inv.total_inc_vat - inv.amount_paid).quantize(Decimal("0.01"))
                ),
            }
        )
    citations = [{"label": inv.invoice_number, "href": f"/invoices/{inv.id}"} for inv in rows]
    if invoices:
        _set_structured_payload(
            ctx,
            {"kind": "overdue_invoices", "invoices": invoices, "citations": citations},
        )
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
async def clear_canvas(ctx: RunContext[NiaDeps]) -> Union[dict[str, Any], str]:
    """Empty the Canvas whiteboard. Call this when the user asks to clear the canvas."""
    denied = _require_nia_use(ctx.deps)
    if denied:
        return denied

    ctx.deps.canvas_spec = empty_canvas_spec()
    payload = canvas_cleared_payload()
    ctx.deps.last_canvas_payload = payload
    _set_structured_payload(ctx, payload)
    return payload


@nia_agent.tool
async def set_canvas(
    ctx: RunContext[NiaDeps],
    title: str,
    components: list[dict[str, Any]],
) -> Union[dict[str, Any], str]:
    """Replace the whole Canvas spec (title + components). Use for 'instead show X'."""
    denied = _require_nia_use(ctx.deps)
    if denied:
        return denied

    spec = set_canvas_spec(title, components)
    if spec is None:
        return "Canvas replace failed: components must be allowlisted bar, line, table, or metric cards."
    return _publish_canvas_spec(ctx, spec)


@nia_agent.tool
async def add_canvas_component(
    ctx: RunContext[NiaDeps],
    component: dict[str, Any],
) -> Union[dict[str, Any], str]:
    """Append one Canvas card and keep the existing cards."""
    denied = _require_nia_use(ctx.deps)
    if denied:
        return denied

    spec = merge_add_canvas_component(_current_canvas(ctx.deps), component)
    if spec is None:
        return (
            "Canvas add failed: component must be an allowlisted bar, line, table, or metric card."
        )
    return _publish_canvas_spec(ctx, spec)


@nia_agent.tool
async def remove_canvas_component(
    ctx: RunContext[NiaDeps],
    component_id: str,
) -> Union[dict[str, Any], str]:
    """Remove a Canvas card by id."""
    denied = _require_nia_use(ctx.deps)
    if denied:
        return denied

    current = _current_canvas(ctx.deps)
    target = component_id.strip()
    if not any(entry.get("id") == target for entry in current.get("components", [])):
        return f"Canvas remove failed: no component with id {target}."
    return _publish_canvas_spec(ctx, drop_canvas_component(current, target))


@nia_agent.tool
async def set_canvas_title(ctx: RunContext[NiaDeps], title: str) -> Union[dict[str, Any], str]:
    """Set the Canvas title without changing cards."""
    denied = _require_nia_use(ctx.deps)
    if denied:
        return denied

    return _publish_canvas_spec(ctx, apply_canvas_title(_current_canvas(ctx.deps), title))


@nia_agent.tool
async def chart_dining_vs_sofas(
    ctx: RunContext[NiaDeps],
    mode: str = "replace",
) -> Union[dict[str, Any], str]:
    """Chart dining vs sofa sales for the current calendar month on Canvas."""
    denied = _require_nia_use(ctx.deps)
    if denied:
        return denied

    spec = await build_dining_vs_sofas_canvas_spec(ctx.deps.db)
    return _apply_chart_spec(ctx, spec, mode)


@nia_agent.tool
async def chart_overdue_invoices(
    ctx: RunContext[NiaDeps],
    mode: str = "replace",
) -> Union[dict[str, Any], str]:
    """Draw overdue invoices (30-day terms) as a Canvas table. Replaces the canvas by default."""
    denied = _require_nia_use(ctx.deps)
    if denied:
        return denied

    spec = await build_overdue_invoices_canvas_spec(ctx.deps.db)
    return _apply_chart_spec(ctx, spec, mode)


@nia_agent.tool
async def chart_sales_by_sku(
    ctx: RunContext[NiaDeps],
    top_n: int = 8,
    mode: str = "replace",
) -> Union[dict[str, Any], str]:
    """Chart top SKU sales this month on Canvas from the sales-by-SKU report."""
    denied = _require_nia_use(ctx.deps)
    if denied:
        return denied

    spec = await build_sales_by_sku_canvas_spec(ctx.deps.db, top_n)
    return _apply_chart_spec(ctx, spec, mode)


@nia_agent.tool
async def chart_stock_on_hand(
    ctx: RunContext[NiaDeps],
    sku: str,
    location: str,
    mode: str = "add",
) -> Union[dict[str, Any], str]:
    """Add a stock-on-hand table for a SKU at a location. Default is append."""
    denied = _require_nia_use(ctx.deps)
    if denied:
        return denied

    spec, error = await build_stock_on_hand_canvas_spec(
        ctx.deps.db,
        sku,
        location,
        ctx.deps.user_id,
    )
    if error or spec is None:
        return error or "Stock on hand chart failed."
    return _apply_chart_spec(ctx, spec, mode)


@nia_agent.tool
async def chart_aged_ar(
    ctx: RunContext[NiaDeps],
    mode: str = "replace",
) -> Union[dict[str, Any], str]:
    """Chart aged receivables buckets on Canvas from the existing aged-AR report."""
    denied = _require_nia_use(ctx.deps)
    if denied:
        return denied

    spec = await build_aged_ar_canvas_spec(ctx.deps.db)
    return _apply_chart_spec(ctx, spec, mode)


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
                "from_location_id": str(from_id),
                "to_location_id": str(to_id),
                "sku_id": str(sku_id),
                "qty": qty,
                "sku": sku.strip(),
                "from_location": from_location.strip(),
                "to_location": to_location.strip(),
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
    payload = {
        "kind": "transfer_draft",
        "transfer_id": str(transfer.id),
        "transfer_number": transfer.transfer_number,
        "status": transfer.status.value,
        "undoable": True,
        "citations": [{"label": transfer.transfer_number, "href": "/transfers"}],
    }
    _set_structured_payload(ctx, payload)
    return payload
