"""Sales and Books draft actions share Firstout's normal pricing and journal rules."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

from pydantic import Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mcp_token import McpToken
from app.permissions import BOOKS_MUTATE, SALES_QUOTES
from app.schemas.journal import JournalCreate
from app.schemas.quote import QuoteCreate
from app.services.journals import JournalService
from app.services.mcp_action_types import Action, Arguments
from app.services.quotes import QuotesService


class QuoteItem(Arguments):
    sku_id: uuid.UUID
    qty: int = Field(strict=True, gt=0, le=10000)


class QuoteDraft(Arguments):
    customer_id: uuid.UUID
    lines: list[QuoteItem] = Field(min_length=1, max_length=50)
    notes: str | None = Field(default=None, max_length=512)


class LedgerLine(Arguments):
    account_id: uuid.UUID
    debit_zar: Decimal = Field(default=Decimal(0), ge=0, max_digits=14, decimal_places=2)
    credit_zar: Decimal = Field(default=Decimal(0), ge=0, max_digits=14, decimal_places=2)


class JournalDraft(Arguments):
    entry_date: datetime.date
    lines: list[LedgerLine] = Field(min_length=2, max_length=50)
    memo: str | None = Field(default=None, max_length=512)


async def _quote(db: AsyncSession, token: McpToken, args: QuoteDraft) -> dict:
    service = QuotesService(db)
    quote = await service.prepare_draft(
        QuoteCreate.model_validate(args.model_dump()), token.user_id
    )
    await service.stage_draft(quote)
    return {
        "id": str(quote.id),
        "number": quote.quote_number,
        "status": quote.status.value,
        "href": "/quotes",
    }


async def _journal(db: AsyncSession, token: McpToken, args: JournalDraft) -> dict:
    service = JournalService(db)
    data = JournalCreate(**args.model_dump(), source="mcp")
    journal = await service.stage_create(data, token.user_id, await service.validate_create(data))
    return {
        "id": str(journal.id),
        "number": journal.journal_number,
        "status": journal.status.value,
        "href": f"/journals?record={journal.id}",
    }


DRAFT_ACTIONS = (
    Action(
        "quotes_create_draft",
        "Sales / Quotes",
        "Draft a quote for a customer at Firstout's current prices. Nothing is sent.",
        QuoteDraft,
        (SALES_QUOTES,),
        _quote,
        "write",
    ),
    Action(
        "journals_create_draft",
        "Books / Journals",
        "Prepare a balanced draft journal for review. Posting is a separate staff action.",
        JournalDraft,
        (BOOKS_MUTATE,),
        _journal,
        "write",
    ),
)
