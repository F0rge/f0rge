"""Two payments must not settle the same invoice balance."""

from __future__ import annotations

import asyncio
import datetime
from decimal import Decimal

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.crud.bill import BillCRUD
from app.crud.tax_invoice import TaxInvoiceCRUD
from app.models.account import Account
from app.models.bill import Bill
from app.models.books_event import BooksEvent
from app.models.customer import Customer
from app.models.document_sequence import DocumentSequence
from app.models.journal import JournalDocumentType, JournalEntry, JournalLine
from app.models.payment import Payment
from app.models.supplier import Supplier
from app.models.tax_invoice import TaxInvoice
from app.models.user import User
from app.schemas.bill import BillCreate, BillLineCreate
from app.schemas.invoice import InvoiceCreate, InvoiceLineCreate
from app.schemas.payment import PaymentCreate
from app.services.bills import BillService
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


def _split_results(results: list[object]) -> tuple[list[object], list[ValidationError]]:
    successes = [result for result in results if not isinstance(result, Exception)]
    rejected = [result for result in results if isinstance(result, ValidationError)]
    unexpected = [
        result
        for result in results
        if isinstance(result, Exception) and not isinstance(result, ValidationError)
    ]
    assert unexpected == [], unexpected
    return successes, rejected


async def _race_two_payments(maker, model, crud, document_id, pay) -> list[object]:
    """Hold the document row, start two payments, then release so they serialise."""
    reads = {"n": 0}
    both_observed = asyncio.Event()
    original_get = crud.get_by_id

    async def _counting_get(self, target_id, *args, **kwargs):
        row = await original_get(self, target_id, *args, **kwargs)
        if target_id == document_id:
            reads["n"] += 1
            if reads["n"] >= 2:
                both_observed.set()
        return row

    crud.get_by_id = _counting_get  # type: ignore[method-assign]
    probe = maker()
    await probe.__aenter__()
    await probe.begin()
    await probe.execute(select(model).where(model.id == document_id).with_for_update())
    tasks = [asyncio.create_task(pay()) for _ in range(2)]
    try:
        try:
            await asyncio.wait_for(both_observed.wait(), timeout=1)
        except asyncio.TimeoutError:
            pass
        await probe.commit()
        return await asyncio.gather(*tasks, return_exceptions=True)
    finally:
        crud.get_by_id = original_get  # type: ignore[method-assign]
        await probe.close()


async def _bank_debits(session: AsyncSession, payment_ids: list) -> Decimal:
    bank_debits = await session.scalar(
        select(func.coalesce(func.sum(JournalLine.debit_zar), 0))
        .join(JournalEntry, JournalLine.entry_id == JournalEntry.id)
        .join(Account, JournalLine.account_id == Account.id)
        .where(
            JournalEntry.document_type == JournalDocumentType.PAYMENT,
            JournalEntry.document_id.in_(payment_ids),
            Account.code == CODE_BANK,
        )
    )
    return Decimal(bank_debits or 0)


async def test_concurrent_partial_invoice_payments_both_apply(async_engine) -> None:
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
        customer = Customer(name="Concurrent partial payer")
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

    assert invoice_id is not None and customer_id is not None and user_id is not None

    async def _pay():
        async with maker() as session:
            return await PaymentService(session).create(
                PaymentCreate(
                    direction="in",
                    invoice_id=invoice_id,
                    amount=Decimal("50.00"),
                    currency="ZAR",
                    paid_on=paid_on,
                ),
                user_id,
            )

    results = await _race_two_payments(maker, TaxInvoice, TaxInvoiceCRUD, invoice_id, _pay)
    try:
        successes, rejected = _split_results(results)
        assert rejected == []
        assert len(successes) == 2
        async with maker() as session:
            invoice = (
                await session.execute(select(TaxInvoice).where(TaxInvoice.id == invoice_id))
            ).scalar_one()
            payments = (
                (await session.execute(select(Payment).where(Payment.invoice_id == invoice_id)))
                .scalars()
                .all()
            )
            assert invoice.amount_paid == Decimal("100.00")
            assert len(payments) == 2
            assert await _bank_debits(session, [payment.id for payment in payments]) == Decimal(
                "100.00"
            )
    finally:
        async with maker() as session:
            async with session.begin():
                payment_ids = select(Payment.id).where(Payment.invoice_id == invoice_id)
                await session.execute(
                    delete(BooksEvent).where(
                        BooksEvent.document_id.in_(payment_ids)
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


async def test_concurrent_partial_invoice_payments_cannot_exceed_the_balance(async_engine) -> None:
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
        customer = Customer(name="Concurrent overlap payer")
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

    assert invoice_id is not None and customer_id is not None and user_id is not None

    async def _pay():
        async with maker() as session:
            return await PaymentService(session).create(
                PaymentCreate(
                    direction="in",
                    invoice_id=invoice_id,
                    amount=Decimal("80.00"),
                    currency="ZAR",
                    paid_on=paid_on,
                ),
                user_id,
            )

    results = await _race_two_payments(maker, TaxInvoice, TaxInvoiceCRUD, invoice_id, _pay)
    try:
        successes, rejected = _split_results(results)
        assert len(successes) == 1
        assert len(rejected) == 1
        assert "still owing" in str(rejected[0])
        async with maker() as session:
            invoice = (
                await session.execute(select(TaxInvoice).where(TaxInvoice.id == invoice_id))
            ).scalar_one()
            payments = (
                (await session.execute(select(Payment).where(Payment.invoice_id == invoice_id)))
                .scalars()
                .all()
            )
            assert invoice.amount_paid == Decimal("80.00")
            assert len(payments) == 1
            assert await _bank_debits(session, [payment.id for payment in payments]) == Decimal(
                "80.00"
            )
    finally:
        async with maker() as session:
            async with session.begin():
                payment_ids = select(Payment.id).where(Payment.invoice_id == invoice_id)
                await session.execute(
                    delete(BooksEvent).where(
                        BooksEvent.document_id.in_(payment_ids)
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


async def test_concurrent_partial_bill_payments_both_apply(async_engine) -> None:
    maker = async_sessionmaker(async_engine, expire_on_commit=False, class_=AsyncSession)
    bill_id = None
    supplier_id = None
    sequences: dict[str, int] = {}
    user_id = None
    paid_on = datetime.date(2026, 10, 1)

    async with maker() as session:
        sequences = await _snapshot_sequences(session)
        user = (
            await session.execute(select(User).where(User.email == "owner@example.com"))
        ).scalar_one()
        user_id = user.id
        supplier = Supplier(name="Concurrent bill supplier", default_currency="ZAR")
        session.add(supplier)
        await session.flush()
        supplier_id = supplier.id
        created = await BillService(session).create(
            BillCreate(
                supplier_id=supplier.id,
                supplier_ref="CONC-1",
                issue_date=paid_on,
                currency="ZAR",
                lines=[BillLineCreate(description="Delivery", qty=1, unit_amount=Decimal("50.00"))],
            ),
            user.id,
        )
        bill_id = created.id
        assert created.amount_foreign == Decimal("50.00")

    assert bill_id is not None and supplier_id is not None and user_id is not None

    async def _pay():
        async with maker() as session:
            return await PaymentService(session).create(
                PaymentCreate(
                    direction="out",
                    bill_id=bill_id,
                    amount=Decimal("20.00"),
                    currency="ZAR",
                    paid_on=paid_on,
                ),
                user_id,
            )

    results = await _race_two_payments(maker, Bill, BillCRUD, bill_id, _pay)
    try:
        successes, rejected = _split_results(results)
        assert rejected == []
        assert len(successes) == 2
        async with maker() as session:
            bill = (await session.execute(select(Bill).where(Bill.id == bill_id))).scalar_one()
            payments = (
                (await session.execute(select(Payment).where(Payment.bill_id == bill_id)))
                .scalars()
                .all()
            )
            assert bill.amount_paid_foreign == Decimal("40.00")
            assert bill.amount_paid_zar == Decimal("40.00")
            assert len(payments) == 2
            assert sum((payment.amount_zar for payment in payments), Decimal(0)) == Decimal("40.00")
    finally:
        async with maker() as session:
            async with session.begin():
                payment_ids = select(Payment.id).where(Payment.bill_id == bill_id)
                await session.execute(
                    delete(BooksEvent).where(
                        BooksEvent.document_id.in_(payment_ids)
                        | (BooksEvent.document_id == bill_id)
                    )
                )
                await session.execute(
                    delete(JournalEntry).where(
                        JournalEntry.document_id.in_(payment_ids)
                        | (JournalEntry.document_id == bill_id)
                    )
                )
                await session.execute(delete(Payment).where(Payment.bill_id == bill_id))
                await session.execute(delete(Bill).where(Bill.id == bill_id))
                await session.execute(delete(Supplier).where(Supplier.id == supplier_id))
                await _restore_sequences(session, sequences)
