from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Optional

from pydantic_ai import Agent
from pydantic_ai.models.openrouter import OpenRouterModel
from pydantic_ai.providers.openrouter import OpenRouterProvider

from app.config import settings

NIA_INSTRUCTIONS = """You are Nia, the in-app assistant for Vellano — a Gauteng furniture retailer back office.

You help shop-floor staff with stock, till, catalogue, transfers, books, and reports questions.
Be concise and practical. Use South African retail context (ZAR, VAT 15%) when relevant.

You must NOT send email, take payment, or file with SARS/RCS/eFiling. You have no tools yet — answer from context only.
"""


@dataclass
class NiaDeps:
    user_id: uuid.UUID
    permissions: list[str]
    page_path: str
    invoice_id: Optional[uuid.UUID] = None
    customer_id: Optional[uuid.UUID] = None
    sku_id: Optional[uuid.UUID] = None


nia_agent = Agent(deps_type=NiaDeps, instructions=NIA_INSTRUCTIONS)


def build_nia_model() -> OpenRouterModel:
    return OpenRouterModel(
        settings.openrouter_model,
        provider=OpenRouterProvider(api_key=settings.openrouter_api_key),
    )
