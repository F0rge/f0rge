"""Rank open invoices and bills against one unmatched bank line."""

from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass
from decimal import Decimal

from app.services.settlement import cents


@dataclass(frozen=True)
class OpenDocument:
    kind: str
    document_id: uuid.UUID
    number: str
    contact_name: str
    outstanding_zar: Decimal
    issue_date: datetime.date
    currency: str
    outstanding_foreign: Decimal
    fx_to_zar: Decimal


@dataclass(frozen=True)
class RankedMatch:
    document: OpenDocument
    confidence: int
    reason: str
    exact_amount: bool
    number_hit: bool

    @property
    def auto_match(self) -> bool:
        return self.exact_amount and self.number_hit


def rank_documents(
    *,
    amount_zar: Decimal,
    transaction_date: datetime.date,
    description: str,
    reference: str | None,
    documents: list[OpenDocument],
) -> list[RankedMatch]:
    bank_abs = cents(abs(amount_zar))
    if bank_abs <= 0:
        return []
    money_in = amount_zar > 0
    haystack = f"{description} {reference or ''}".lower()
    ranked: list[RankedMatch] = []
    for document in documents:
        if money_in and document.kind != "invoice":
            continue
        if not money_in and document.kind != "bill":
            continue
        outstanding = cents(document.outstanding_zar)
        if outstanding <= 0 or bank_abs > outstanding:
            continue
        if document.currency.upper() != "ZAR" and bank_abs != outstanding:
            continue
        exact = bank_abs == outstanding
        score = 60 if exact else 35
        reasons = [
            "exact outstanding balance" if exact else "part of the outstanding balance",
        ]
        number = document.number.strip()
        number_hit = len(number) >= 4 and number.lower() in haystack
        if number_hit:
            score += 30
            reasons.append(f"{number} is in the description")
        name = document.contact_name.strip()
        if len(name) >= 4 and name.lower() in haystack:
            score += 20
            reasons.append(f"{name} is in the description")
        days = abs((transaction_date - document.issue_date).days)
        if days <= 7:
            score += 10
            reasons.append("within 7 days of the document date")
        elif days <= 30:
            score += 5
            reasons.append("within 30 days of the document date")
        ranked.append(
            RankedMatch(
                document=document,
                confidence=min(score, 100),
                reason="; ".join(reasons),
                exact_amount=exact,
                number_hit=number_hit,
            )
        )
    ranked.sort(
        key=lambda item: (
            -item.confidence,
            abs((transaction_date - item.document.issue_date).days),
            item.document.number,
        )
    )
    return ranked[:5]


def unique_auto_match(ranked: list[RankedMatch]) -> RankedMatch | None:
    hits = [item for item in ranked if item.auto_match]
    if len(hits) == 1:
        return hits[0]
    return None
