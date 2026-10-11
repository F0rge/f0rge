"""Two payments must not settle the same invoice balance."""

from __future__ import annotations

import asyncio
import datetime
from decimal import Decimal

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.crud.tax_invoice import TaxInvoiceCRUD
from app.models.account import Account
from app.models.books_event import BooksEvent
from app.models.customer import Customer
from app.models.document_sequence import DocumentSequence
from app.models.journal import JournalDocumentType, JournalEntry, JournalLine
from app.models.payment import Payment
from app.models.tax_invoice import TaxInvoice
from app.models.user import User
from app.schemas.invoice import InvoiceCreate, InvoiceLineCreate
from app.schemas.payment import PaymentCreate
from app.services.chart_of_accounts import CODE_BANK
from app.services.invoices import InvoiceService
from app.services.payments import PaymentService
from f0rge_core.exceptions import ValidationError


async def _snapshot_sequences(session: AsyncSession) -> dict[str, int]:
    rows = (await session.execute(select(DocumentSequence))).scalars().all()
    return {row.doc_type: int(row.next_value) for row in rows}


async def _restore_sequences(session: AsyncSession, before: dict[str, int]) -> None:
    rows = (await session.execute(select(DocumentSequence))).scalars().all()
    for row in rows:
        if row.doc_type in before:
            row.next_value = before[row.doc_type]
        else:
            await session.delete(row)


async def test_concurrent_payments_cannot_settle_the_same_balance(async_engine) -> None:
    maker = async_sessionmaker(async_engine, expire_on_commit=False, class_=AsyncSession)
    invoice_id = None
    customer_id = None
    sequences: dict[str, int] = {}
    user_id = None
    paid_on = datetime.date(2026, 10, 1)

    async with maker() as session:
        sequences = await _snapshot_sequences(session)
        user = (
            await session.execute(select(User).where(User.email == "owner@example.com"))
        ).scalar_one()
        user_id = user.id
        customer = Customer(name="Concurrent payer")
        session.add(customer)
        await session.flush()
        customer_id = customer.id
        created = await InvoiceService(session).create(
            InvoiceCreate(
                customer_id=customer.id,
                issue_date=paid_on,
                lines=[
                    InvoiceLineCreate(
                        description="Sofa",
                        qty=1,
                        unit_ex_vat=Decimal("100.00"),
                    )
                ],
            ),
            user.id,
        )
        invoice_id = created.id
        assert created.total_inc_vat == Decimal("115.00")
        assert created.amount_paid == Decimal("0.00")

    assert invoice_id is not None
    assert customer_id is not None
    assert user_id is not None

    reads = {"n": 0}
    both_observed = asyncio.Event()
    original_get = TaxInvoiceCRUD.get_by_id

    async def _counting_get(self, target_id, *args, **kwargs):
        row = await original_get(self, target_id, *args, **kwargs)
        if target_id == invoice_id:
            reads["n"] += 1
            if reads["n"] >= 2:
                both_observed.set()
        return row

    TaxInvoiceCRUD.get_by_id = _counting_get  # type: ignore[method-assign]

    probe = maker()
    await probe.__aenter__()
    await probe.begin()
    await probe.execute(select(TaxInvoice).where(TaxInvoice.id == invoice_id).with_for_update())

    async def _pay():
        async with maker() as session:
            return await PaymentService(session).create(
                PaymentCreate(
                    direction="in",
                    invoice_id=invoice_id,
                    amount=Decimal("115.00"),
                    currency="ZAR",
                    paid_on=paid_on,
                ),
                user_id,
            )

    try:
        tasks = [asyncio.create_task(_pay()) for _ in range(2)]
        try:
            await asyncio.wait_for(both_observed.wait(), timeout=1)
        except asyncio.TimeoutError:
            pass
        await probe.commit()
        results = await asyncio.gather(*tasks, return_exceptions=True)
    finally:
        TaxInvoiceCRUD.get_by_id = original_get  # type: ignore[method-assign]
        await probe.close()

    try:
        successes = [result for result in results if not isinstance(result, Exception)]
        rejected = [result for result in results if isinstance(result, ValidationError)]
        unexpected = [
            result
            for result in results
            if isinstance(result, Exception) and not isinstance(result, ValidationError)
        ]
        assert unexpected == [], unexpected
        assert len(successes) == 1, (len(successes), len(rejected), reads["n"])
        assert len(rejected) == 1

        async with maker() as session:
            invoice = (
                await session.execute(select(TaxInvoice).where(TaxInvoice.id == invoice_id))
            ).scalar_one()
            payments = (
                (await session.execute(select(Payment).where(Payment.invoice_id == invoice_id)))
                .scalars()
                .all()
            )
            bank_debits = await session.scalar(
                select(func.coalesce(func.sum(JournalLine.debit_zar), 0))
                .join(JournalEntry, JournalLine.entry_id == JournalEntry.id)
                .join(Account, JournalLine.account_id == Account.id)
                .where(
                    JournalEntry.document_type == JournalDocumentType.PAYMENT,
                    JournalEntry.document_id.in_([payment.id for payment in payments]),
                    Account.code == CODE_BANK,
                )
            )
            assert invoice.amount_paid == Decimal("115.00")
            assert invoice.total_inc_vat == Decimal("115.00")
            assert len(payments) == 1
            assert payments[0].amount == Decimal("115.00")
            assert bank_debits == Decimal("115.00")
    finally:
        async with maker() as session:
            async with session.begin():
                payment_ids = select(Payment.id).where(Payment.invoice_id == invoice_id)
                document_ids = select(Payment.id).where(Payment.invoice_id == invoice_id)
                await session.execute(
                    delete(BooksEvent).where(
                        BooksEvent.document_id.in_(document_ids)
                        | (BooksEvent.document_id == invoice_id)
                    )
                )
                await session.execute(
                    delete(JournalEntry).where(
                        JournalEntry.document_id.in_(payment_ids)
                        | (JournalEntry.document_id == invoice_id)
                    )
                )
                await session.execute(delete(Payment).where(Payment.invoice_id == invoice_id))
                await session.execute(delete(TaxInvoice).where(TaxInvoice.id == invoice_id))
                await session.execute(delete(Customer).where(Customer.id == customer_id))
                await _restore_sequences(session, sequences)
