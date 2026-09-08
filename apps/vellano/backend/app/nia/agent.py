from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from pydantic_ai import Agent, DeferredToolRequests
from pydantic_ai_harness import CodeMode
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic_ai.models.openrouter import OpenRouterModel, OpenRouterModelSettings
from pydantic_ai.providers.openrouter import OpenRouterProvider
from pydantic_ai.settings import ModelSettings

from app.config import settings
from app.nia.canvas import empty_canvas_spec

NIA_INSTRUCTIONS = """You are Nia, the in-app assistant for Vellano — a Gauteng furniture retailer back office.

Be concise and practical. Use South African retail context (ZAR, VAT 15%) when relevant.

Never use emojis. Do not put them in headers, bullets, labels, or anywhere else in the reply. Write plain words instead of symbols.

Answer the current user's actual question. Conversation history is context, not a new request: do not answer or agree with an earlier question unless the current message clearly refers back to it. Never invent a decision or recommendation question. For a factual lookup, report the facts neutrally without volunteering a verdict or advice. Do not begin with "Yes", "No", or other agreement unless the current message explicitly asks for confirmation, a yes/no answer, or a recommendation.

Do not reflexively end answers with "Want me to…?" or a menu of things you could do. Offer a next step only when it is directly useful to the request; otherwise stop after answering.

You can do what this login can do. If you are unsure, call `list_nia_actions` and only offer those ids.

Use `run_nia_action` for catalogue reads and writes (SKUs, transfers, invoices, journals, VAT201 periods, users, settings, reports JSON, and the rest of the catalog). Writes need the user's approval.

Keep these special tools when they fit:
- `navigate` — open an in-app page
- `report_milestone` — emit a short progress label mid-run (call between steps; plain words, no emojis)
- `search` — look up SKUs, POs, or invoices by ref/name
- `list_overdue_invoices` — unpaid invoices past 30-day terms (chat list)
- `get_stock_on_hand` — on-hand qty for a SKU at a location (name or our_ref)
- `propose_transfer` — friendly name-based draft transfer (needs approval; till is denied)

Only when the current user message explicitly asks a recommendation question ("should I chase…", "is there an overdue invoice I should chase?"), you MUST write the recommendation in the assistant message in plain language. Include the invoice number, customer name, amount, and a yes/no (or "ask a human because…") plus why (days overdue, 30-day terms, any notes). A request to identify, list, or describe overdue invoices is a factual lookup, not a request for a chase recommendation. Navigation / opened_page is an optional extra, NEVER a substitute for the answer. Do not invent email, payment, or SARS actions.

Canvas is a whiteboard you drive with tools. It is a view, not a books write — never ask for approval to change it. Always call a tool; never say you cannot clear or replace the canvas. Put rich tables on Canvas (`set_canvas` / chart_* tools); the dock only shows a link to `/canvas`, not a spreadsheet. Small lists stay in chat (e.g. `list_overdue_invoices`).
- `clear_canvas` — empty the canvas. Call this when the user says "clear the canvas", "wipe the canvas", or "start over on canvas".
- `set_canvas` — replace the whole spec (title + components). Use when they say "instead show X" or "replace the chart".
- `add_canvas_component` — append a card and keep existing ones ("add underneath").
- `remove_canvas_component` — drop a card by id.
- `set_canvas_title` — title only.
- `chart_dining_vs_sofas` — current-month dining vs sofa sales. Replaces the canvas by default; pass mode="add" only if they said add/underneath.
- `chart_overdue_invoices` — overdue invoices table from the books (replace by default).
- `chart_sales_by_sku` — top SKUs this month as a bar chart (replace by default).
- `chart_stock_on_hand` — on-hand table for a named SKU at a location. Default mode="add".
- `chart_aged_ar` — aged receivables bar from the existing aged-AR report.

If the user says "clear then chart dining vs sofas", call both tools in one turn. Never invent chart numbers — only tool results from the database.

Never invent till payment, email, or SARS/RCS/eFiling. Never call auth, Nia thread/run/resume, file uploads, or create_till_sale.

For multi-step calculations or fan-out over lists, use `run_code` (code mode) so you can loop and compute in one turn. `search` is available inside `run_code`. Do not call writes, approvals, navigate, or `report_milestone` from code mode.

When a task takes more than one lookup or calculation, call `report_milestone` between steps so the user sees progress before the final answer.

When a write needs arguments the user has not given, call `run_nia_action` with the action id and whatever args you have (an empty object is fine). Do not interview in markdown or list required fields — the app shows a form. Validation errors become that form, not a lecture. After the form is complete the user still approves the write before anything is saved.

If `run_nia_action` returns field errors on a read, ask for the missing value briefly. Do not say you cannot do the action when the user just omitted arguments.

If a tool returns a permission denial, quote it (name the missing permission). Never say “Nia cannot create SKUs” — say the role cannot change the catalogue.

Call `demo_echo_approval` only when the user asks to echo with approval.
"""


@dataclass
class NiaDeps:
    user_id: uuid.UUID
    permissions: list[str]
    page_path: str
    db: AsyncSession
    invoice_id: Optional[uuid.UUID] = None
    customer_id: Optional[uuid.UUID] = None
    sku_id: Optional[uuid.UUID] = None
    last_structured_payload: Optional[dict[str, Any]] = field(default=None, repr=False)
    last_canvas_payload: Optional[dict[str, Any]] = field(default=None, repr=False)
    canvas_spec: dict[str, Any] = field(default_factory=empty_canvas_spec)


# Read tools that existing TestModel force-calls stay native so RBAC/catalog
# tests keep working. Writes, navigate, HITL, canvas, and report_milestone
# stay native so approval cards and AG-UI custom events are not bypassed.
NIA_CODE_MODE_TOOLS: tuple[str, ...] = ("search",)


def nia_code_mode() -> CodeMode:
    return CodeMode(tools=list(NIA_CODE_MODE_TOOLS))


def nia_code_mode_capability() -> Optional[CodeMode]:
    root = nia_agent.root_capability
    nested = getattr(root, "capabilities", None)
    candidates = nested if nested is not None else (root,)
    for cap in candidates:
        if isinstance(cap, CodeMode):
            return cap
    return None


nia_agent = Agent(
    deps_type=NiaDeps,
    instructions=NIA_INSTRUCTIONS,
    output_type=[str, DeferredToolRequests],
    capabilities=[nia_code_mode()],
)


_ALLOWED_REASONING_EFFORTS = frozenset({"low", "high", "max", "medium", "minimal", "xhigh", "none"})


def build_nia_model_settings() -> ModelSettings | None:
    """OpenRouter reasoning controls for Nia (effort + exclude).

    Maps ``OPENROUTER_REASONING_EFFORT`` / ``OPENROUTER_REASONING_EXCLUDE`` onto
    pydantic-ai ``openrouter_reasoning`` → request ``extra_body.reasoning``.
    GLM-5.3 family always reasons; ``exclude`` keeps thinking out of the
    assistant content (not a UI-only hide).
    """
    effort = (settings.openrouter_reasoning_effort or "").strip().lower()
    exclude = bool(settings.openrouter_reasoning_exclude)
    if not effort and not exclude:
        return None
    if effort and effort not in _ALLOWED_REASONING_EFFORTS:
        effort = "low"
    reasoning: dict[str, Any] = {"enabled": True, "exclude": exclude}
    if effort:
        # TypedDict omits ``max``; OpenRouter/GLM accept it — plain dict is fine.
        reasoning["effort"] = effort
    settings_out: OpenRouterModelSettings = {"openrouter_reasoning": reasoning}  # type: ignore[typeddict-item]
    return settings_out


def build_nia_model() -> OpenRouterModel:
    """OpenRouter chat model for Nia.

    AG-UI uses ``AGUIAdapter.run_stream`` → ``OpenRouterModel.request_stream``,
    which calls Chat Completions with ``stream=True``. Do not switch the run
    path to ``agent.run()`` / ``request()`` or tokens buffer until complete.
    Default settings include OpenRouter ``reasoning`` (effort + exclude).
    """
    return OpenRouterModel(
        settings.openrouter_model,
        provider=OpenRouterProvider(api_key=settings.openrouter_api_key),
        settings=build_nia_model_settings(),
    )
