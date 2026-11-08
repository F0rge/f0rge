"""Shared customer name, email, and South African phone matching.

Search is partial. Duplicate checks are exact after the same normalisation:
case-insensitive names with collapsed whitespace, case-insensitive emails,
and phone digits with +27 / 27 / leading 0 treated as the same national number.
"""

from __future__ import annotations

import re
from typing import Optional

from sqlalchemy import func, or_
from sqlalchemy.sql.elements import ColumnElement

from app.models.customer import Customer

_NON_DIGIT = re.compile(r"\D+")
_SPACES = re.compile(r"\s+")

NAME_UNIQUE_INDEX = "ix_customers_name_lower"


def fold_name(value: Optional[str]) -> str:
    if not value:
        return ""
    return _SPACES.sub(" ", value).strip().casefold()


def fold_email(value: Optional[str]) -> str:
    if not value:
        return ""
    return value.strip().casefold()


def national_phone_digits(raw: Optional[str]) -> str:
    """Digits with 0027 / a full 27 prefix removed, then one leading 0.

    Must match ``PHONE_NATIONAL_SQL`` on ``Customer.phone_national``.
    """
    if raw is None or not raw.strip():
        return ""
    digits = _NON_DIGIT.sub("", raw)
    if not digits:
        return ""
    if digits.startswith("0027"):
        digits = digits[4:]
    elif digits.startswith("27") and len(digits) >= 11:
        digits = digits[2:]
    if digits.startswith("0"):
        digits = digits[1:]
    return digits


def phone_search_needles(raw: str) -> list[str]:
    """Partial phone keys. Short country-code prefixes also try the national rest."""
    digits = _NON_DIGIT.sub("", raw or "")
    if len(digits) < 3:
        return []
    needles: list[str] = []

    def add(value: str) -> None:
        if len(value) >= 2 and value not in needles:
            needles.append(value)

    add(national_phone_digits(raw))
    if digits.startswith("0027"):
        add(national_phone_digits(digits[4:]))
    elif digits.startswith("27"):
        rest = digits[2:]
        if rest.startswith("0"):
            rest = rest[1:]
        add(rest)
    elif digits.startswith("0"):
        add(digits[1:])
    return needles


def contains_pattern(term: str) -> str:
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def customer_search_clause(q: Optional[str]) -> Optional[ColumnElement[bool]]:
    term = (q or "").strip()
    if not term:
        return None
    pattern = contains_pattern(term)
    clauses: list[ColumnElement[bool]] = [
        Customer.name.ilike(pattern, escape="\\"),
        Customer.email.ilike(pattern, escape="\\"),
    ]
    for needle in phone_search_needles(term):
        clauses.append(Customer.phone_national.ilike(contains_pattern(needle), escape="\\"))
    return or_(*clauses)


def name_duplicate_clause(name_key: str) -> ColumnElement[bool]:
    folded = func.lower(func.regexp_replace(func.btrim(Customer.name), r"\s+", " ", "g"))
    return folded == name_key


def email_duplicate_clause(email_key: str) -> ColumnElement[bool]:
    return func.lower(func.btrim(Customer.email)) == email_key
