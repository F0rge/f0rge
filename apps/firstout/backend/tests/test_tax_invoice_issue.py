"""Tax invoice issue: the invariants every issued tax invoice shares, whichever document issues it."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.books_event import BooksDocumentType, BooksEvent, BooksEventAction
from app.models.customer import Customer
from app.models.journal import JournalDocumentType, JournalEntry, JournalLine
from app.models.tax_invoice import InvoiceLine, TaxInvoice
from app.services.tax_invoice_issue import Deposits, TaxInvoiceIssue
from f0rge_core.exceptions import ConflictError
from tests.test_books_periods import _lock_books_period_for_today

TODAY = datetime.date.today()


def _lines() -> list[InvoiceLine]:
    # Already priced by the caller; the issue never reprices.
    return [
        InvoiceLine(
            description="Chair",
            qty=1,
            unit_ex_vat=Decimal("100.00"),
            ex_vat=Decimal("100.00"),
            vat_amount=Decimal("15.00"),
            inc_vat=Decimal("115.00"),
            sort_order=0,
        ),
        InvoiceLine(
            description="Cushion",
            qty=3,
            unit_ex_vat=Decimal("11.11"),
            ex_vat=Decimal("33.33"),
            vat_amount=Decimal("5.00"),
            inc_vat=Decimal("38.33"),
            sort_order=1,
        ),
    ]


async def _customer(owner_client: AsyncClient, db: AsyncSession, terms_days: int) -> Customer:
    resp = await owner_client.post("/api/v1/customers", json={"name": f"Issue {uuid.uuid4()}"})
    assert resp.status_code == 201, resp.text
    customer = await db.get(Customer, uuid.UUID(resp.json()["id"]))
    assert customer is not None
    customer.payment_terms_days = terms_days
    return customer


async def _journal(
    db: AsyncSession, document_type: JournalDocumentType, document_id: uuid.UUID
) -> list[tuple[str, str, Decimal, Decimal]]:
    rows = await db.execute(
        select(JournalEntry.memo, Account.code, JournalLine.debit_zar, JournalLine.credit_zar)
        .join(JournalLine, JournalLine.entry_id == JournalEntry.id)
        .join(Account, Account.id == JournalLine.account_id)
        .where(
            JournalEntry.document_type == document_type,
            JournalEntry.document_id == document_id,
        )
    )
    return sorted(rows.tuples().all())


async def test_issue_numbers_posts_and_records(
    owner_client: AsyncClient, async_db: AsyncSession
) -> None:
    customer = await _customer(owner_client, async_db, terms_days=7)
    issue = TaxInvoiceIssue(async_db)

    first = await issue.issue(
        customer=customer,
        issue_date=TODAY,
        lines=_lines(),
        prices_include_vat=True,
        memo="Test tax invoice",
        actor_user_id=None,
        event_note="credit override: trusted",
    )
    second = await issue.issue(
        customer=customer,
        issue_date=TODAY,
        due_date=TODAY + datetime.timedelta(days=60),
        lines=_lines(),
        prices_include_vat=False,
        memo="Test tax invoice",
        actor_user_id=None,
    )

    # Numbered, one after the other.
    prefix, number = first.invoice_number.rsplit("-", 1)
    assert second.invoice_number == f"{prefix}-{int(number) + 1:0{len(number)}d}"
    # Totals are the sum of the priced lines; nothing is paid yet.
    assert (first.subtotal_ex_vat, first.vat_amount, first.total_inc_vat) == (
        Decimal("133.33"),
        Decimal("20.00"),
        Decimal("153.33"),
    )
    assert first.amount_paid == Decimal(0)
    # Due date: the customer's terms unless the caller set one.
    assert first.due_date == TODAY + datetime.timedelta(days=7)
    assert second.due_date == TODAY + datetime.timedelta(days=60)

    # A balanced Dr AR / Cr sales / Cr VAT journal on the issue date.
    journal = await _journal(async_db, JournalDocumentType.INVOICE, first.id)
    memo = f"Test tax invoice {first.invoice_number}"
    assert journal == [
        (memo, "1200", Decimal("153.33"), Decimal("0.00")),
        (memo, "2200", Decimal("0.00"), Decimal("20.00")),
        (memo, "4000", Decimal("0.00"), Decimal("133.33")),
    ]
    assert sum(row[2] for row in journal) == sum(row[3] for row in journal)

    # One books event per issued invoice, carrying the caller's note.
    events = (
        (
            await async_db.execute(
                select(BooksEvent).where(
                    BooksEvent.document_type == BooksDocumentType.INVOICE,
                    BooksEvent.document_id.in_([first.id, second.id]),
                )
            )
        )
        .scalars()
        .all()
    )
    assert sorted((e.document_id == first.id, e.action, e.note) for e in events) == [
        (False, BooksEventAction.CREATED, None),
        (True, BooksEventAction.CREATED, "credit override: trusted"),
    ]


@pytest.mark.parametrize("deposit", ["153.33", "50.00", "0"])
async def test_issue_applies_deposits(
    owner_client: AsyncClient, async_db: AsyncSession, deposit: str
) -> None:
    customer = await _customer(owner_client, async_db, terms_days=0)
    source_id = uuid.uuid4()

    invoice = await TaxInvoiceIssue(async_db).issue(
        customer=customer,
        issue_date=TODAY,
        lines=_lines(),
        prices_include_vat=True,
        memo="Test tax invoice",
        actor_user_id=None,
        deposits=Deposits(source_id=source_id, memo="Apply test deposits", amount=Decimal(deposit)),
    )

    amount = Decimal(deposit)
    assert invoice.amount_paid == amount
    expected = (
        [
            ("Apply test deposits", "1200", Decimal("0.00"), amount),
            ("Apply test deposits", "2300", amount, Decimal("0.00")),
        ]
        if amount > 0
        else []
    )
    assert await _journal(async_db, JournalDocumentType.PAYMENT, source_id) == expected


async def test_issue_refuses_a_locked_period(
    owner_client: AsyncClient, async_db: AsyncSession
) -> None:
    customer = await _customer(owner_client, async_db, terms_days=0)
    await _lock_books_period_for_today(owner_client)
    before = await async_db.scalar(select(func.count()).select_from(TaxInvoice))

    with pytest.raises(ConflictError, match="Books period is locked for this date"):
        await TaxInvoiceIssue(async_db).issue(
            customer=customer,
            issue_date=TODAY,
            lines=_lines(),
            prices_include_vat=True,
            memo="Test tax invoice",
            actor_user_id=None,
        )

    assert await async_db.scalar(select(func.count()).select_from(TaxInvoice)) == before


async def test_issue_defaults_to_30_days_without_customer_terms_or_team_settings(
    owner_client: AsyncClient, async_db: AsyncSession
) -> None:
    from sqlalchemy import delete

    from app.models.team_settings import TeamSettings

    customer = await _customer(owner_client, async_db, terms_days=0)
    customer.payment_terms_days = None
    await async_db.execute(delete(TeamSettings))
    assert await async_db.scalar(select(func.count()).select_from(TeamSettings)) == 0

    invoice = await TaxInvoiceIssue(async_db).issue(
        customer=customer,
        issue_date=TODAY,
        lines=_lines(),
        prices_include_vat=True,
        memo="Test tax invoice",
        actor_user_id=None,
    )

    assert invoice.due_date == TODAY + datetime.timedelta(days=30)
