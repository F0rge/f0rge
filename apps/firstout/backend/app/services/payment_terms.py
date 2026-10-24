from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Optional

from app.models.customer import Customer
from app.models.team_settings import DEFAULT_PAYMENT_TERMS_DAYS, TeamSettings

DEFAULT_TERMS_DAYS = DEFAULT_PAYMENT_TERMS_DAYS


def effective_terms_days(customer: Customer, team_settings: TeamSettings) -> int:
    if customer.payment_terms_days is not None:
        return customer.payment_terms_days
    return team_settings.payment_terms_days


def compute_due_date(
    issue_date: datetime.date,
    customer: Customer,
    team_settings: TeamSettings,
) -> datetime.date:
    return issue_date + datetime.timedelta(days=effective_terms_days(customer, team_settings))


def effective_due_date(
    issue_date: datetime.date,
    due_date: Optional[datetime.date],
) -> datetime.date:
    """Due date for display and overdue math.

    Snapshotted ``due_date`` wins. Legacy null rows keep the pre-settings 30-day
    clock — never current customer or team terms.
    """
    if due_date is not None:
        return due_date
    return issue_date + datetime.timedelta(days=DEFAULT_TERMS_DAYS)


def display_terms_days(
    due_date: Optional[datetime.date],
    customer: Customer,
    team_settings: TeamSettings,
) -> int:
    if due_date is None:
        return DEFAULT_TERMS_DAYS
    return effective_terms_days(customer, team_settings)


def invoice_open_balance_expr():
    """Collectible balance: invoice total, minus payments, minus credit notes."""
    from sqlalchemy import func, select

    from app.models.credit_note import CreditNote
    from app.models.tax_invoice import TaxInvoice

    credited = (
        select(func.coalesce(func.sum(CreditNote.total_inc_vat), 0))
        .where(CreditNote.invoice_id == TaxInvoice.id)
        .correlate(TaxInvoice)
        .scalar_subquery()
    )
    return TaxInvoice.total_inc_vat - TaxInvoice.amount_paid - credited


def invoice_collectible_balance(invoice) -> Decimal:
    credited = Decimal(0)
    if invoice.credit_note is not None:
        credited = invoice.credit_note.total_inc_vat
    return invoice.total_inc_vat - invoice.amount_paid - credited


def invoice_overdue_predicate(as_of: datetime.date):
    """SQLAlchemy-friendly overdue filter for open invoices (null due_date → 30 days).

    Due-today is current on both paths: snapshotted ``due_date < as_of`` and
    legacy ``issue_date < as_of - 30``. A credited invoice is not overdue.
    """
    from sqlalchemy import and_, or_

    from app.models.tax_invoice import TaxInvoice

    balance = invoice_open_balance_expr()
    legacy_cutoff = as_of - datetime.timedelta(days=DEFAULT_TERMS_DAYS)
    return and_(
        TaxInvoice.is_archive.is_(False),
        balance > 0,
        or_(
            and_(TaxInvoice.due_date.is_not(None), TaxInvoice.due_date < as_of),
            and_(TaxInvoice.due_date.is_(None), TaxInvoice.issue_date < legacy_cutoff),
        ),
    )
