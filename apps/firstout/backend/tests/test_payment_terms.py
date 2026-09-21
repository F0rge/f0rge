"""Payment-terms helpers: due-today clock and legacy 30-day fallback (no_db)."""

from __future__ import annotations

import datetime
from types import SimpleNamespace

import pytest
from sqlalchemy.dialects import postgresql

from app.services.payment_terms import (
    DEFAULT_TERMS_DAYS,
    display_terms_days,
    effective_due_date,
    invoice_overdue_predicate,
)

pytestmark = pytest.mark.no_db


def test_effective_due_date_prefers_snapshot() -> None:
    issue = datetime.date(2026, 8, 1)
    due = datetime.date(2026, 8, 15)
    assert effective_due_date(issue, due) == due


def test_effective_due_date_null_uses_fixed_30_not_current_terms() -> None:
    issue = datetime.date(2026, 8, 1)
    assert effective_due_date(issue, None) == datetime.date(2026, 8, 31)
    assert DEFAULT_TERMS_DAYS == 30


def test_display_terms_days_null_due_ignores_current_terms() -> None:
    customer = SimpleNamespace(payment_terms_days=7)
    team = SimpleNamespace(payment_terms_days=14)
    assert display_terms_days(None, customer, team) == 30
    assert display_terms_days(datetime.date(2026, 8, 15), customer, team) == 7


def test_overdue_predicate_uses_strict_less_than_on_both_paths() -> None:
    as_of = datetime.date(2026, 9, 14)
    sql = str(
        invoice_overdue_predicate(as_of).compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    assert "due_date <" in sql
    assert "issue_date <" in sql
    assert "issue_date <=" not in sql
    assert "2026-08-15" in sql
