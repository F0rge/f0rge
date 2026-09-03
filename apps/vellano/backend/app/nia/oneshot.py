from __future__ import annotations

from typing import Optional

from app.nia.agent import NiaDeps
from app.nia.canvas import (
    CANVAS_CLEARED_KIND,
    CANVAS_SPEC_KIND,
    build_dining_vs_sofas_canvas_spec,
    build_sales_by_sku_canvas_spec,
)

_SKU_TOKEN = "sku"
_SKU_WRITE_HINTS = ("create", "draft", "new", "colour", "color")
_CHART_HINTS = (
    "chart",
    "dining vs",
    "best-sell",
    "bestsell",
    "best selling",
    "best seller",
    "sales by sku",
)


def is_compound_chart_write(prompt: str) -> bool:
    """True only when the user asked for a chart/ranking and a SKU write together."""
    text = (prompt or "").lower()
    if _SKU_TOKEN not in text:
        return False
    if not any(hint in text for hint in _SKU_WRITE_HINTS):
        return False
    return any(hint in text for hint in _CHART_HINTS)


def chart_kind_for_compound_prompt(prompt: str) -> Optional[str]:
    """Which chart to ensure. Conservative — None for SKU-only prompts."""
    if not is_compound_chart_write(prompt):
        return None
    text = prompt.lower()
    if "dining" in text:
        return "dining_vs_sofas"
    if (
        "best-sell" in text
        or "bestsell" in text
        or "best selling" in text
        or "best seller" in text
        or "sales by sku" in text
    ):
        return "sales_by_sku"
    return "dining_vs_sofas"


def should_persist_canvas_ahead(
    deps: NiaDeps,
    outgoing: Optional[dict],
) -> bool:
    """Persist this-run canvas before a HITL/fields (or other non-canvas) card."""
    if not deps.canvas_updated:
        return False
    if outgoing is None:
        return True
    kind = outgoing.get("kind")
    return kind not in (CANVAS_SPEC_KIND, CANVAS_CLEARED_KIND)


async def ensure_oneshot_chart(deps: NiaDeps, prompt: str) -> None:
    """If a compound chart+write prompt never published canvas this run, publish now."""
    if deps.canvas_updated:
        return
    kind = chart_kind_for_compound_prompt(prompt)
    if kind is None:
        return
    if kind == "sales_by_sku":
        spec = await build_sales_by_sku_canvas_spec(deps.db)
    else:
        spec = await build_dining_vs_sofas_canvas_spec(deps.db)
    deps.canvas_spec = spec
    deps.canvas_updated = True
