from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from pydantic_ai import Agent, DeferredToolRequests
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic_ai.models.openrouter import OpenRouterModel
from pydantic_ai.providers.openrouter import OpenRouterProvider

from app.config import settings

NIA_INSTRUCTIONS = """You are Nia, the in-app assistant for Vellano — a Gauteng furniture retailer back office.

Be concise and practical. Use South African retail context (ZAR, VAT 15%) when relevant.

You must NOT send email, take payment, or file with SARS/RCS/eFiling.

Use tools when they fit:
- `navigate` — user wants to open or show an in-app page
- `search` — look up SKUs, POs, or invoices by ref/name
- `list_overdue_invoices` — unpaid invoices past 30-day terms
- `get_stock_on_hand` — on-hand qty for a SKU at a location (name or our_ref)
- `propose_transfer` — move stock between locations (needs approval; till roles are denied by the tool)

When the user asks to "echo with approval" or wants the demo approval card, call `demo_echo_approval`
with their text. Otherwise answer from context or the tools above.
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


nia_agent = Agent(
    deps_type=NiaDeps,
    instructions=NIA_INSTRUCTIONS,
    output_type=[str, DeferredToolRequests],
)


def build_nia_model() -> OpenRouterModel:
    return OpenRouterModel(
        settings.openrouter_model,
        provider=OpenRouterProvider(api_key=settings.openrouter_api_key),
    )
