"""VAT conversions at an explicit rate (Firstout ADR 0003: no hard-coded rate).

A sale document converts at the rate it stores (``vat_rate``); anything priced today
converts at the team's ``vat_rate`` setting, read with ``current_vat_rate``.
"""

from __future__ import annotations

from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.team_settings import TeamSettingsCRUD
from app.crud.user import TeamCRUD
from app.models.team_settings import DEFAULT_VAT_RATE
from f0rge_core.exceptions import ValidationError

CENT = Decimal("0.01")


def ex_to_inc(ex: Decimal, vat_rate: Decimal) -> Decimal:
    return (ex * (1 + vat_rate)).quantize(CENT, rounding=ROUND_HALF_UP)


def inc_to_ex(inc: Decimal, vat_rate: Decimal) -> Decimal:
    return (inc / (1 + vat_rate)).quantize(CENT, rounding=ROUND_HALF_UP)


def retail_inc_to_ex(inc: Decimal, vat_rate: Decimal) -> Decimal:
    """Preserve the catalogue's retail cents with extra ex-VAT precision if needed."""
    net = inc_to_ex(inc, vat_rate)
    # Keep the old conversion for legacy inputs with sub-cent retail amounts.
    if inc != inc.quantize(CENT, rounding=ROUND_HALF_UP) or ex_to_inc(net, vat_rate) == inc:
        return net
    # Truncation keeps the net price on the same side of a half-cent boundary
    # for invoicing. With VAT at most 100%, this loses under 0.0002 of gross.
    return (inc / (1 + vat_rate)).quantize(Decimal("0.0001"), rounding=ROUND_DOWN)


def vat_percent(vat_rate: Decimal) -> Decimal:
    """0.15 → 15.00, as printed and returned beside the rate."""
    return (vat_rate * 100).quantize(CENT)


def validate_non_negative_price(value: Decimal, field_name: str) -> None:
    if value < 0:
        raise ValidationError(f"{field_name} must not be negative")


def inc_vat_or_none(ex_vat: Optional[Decimal], vat_rate: Decimal) -> Optional[Decimal]:
    if ex_vat is None:
        return None
    return ex_to_inc(ex_vat, vat_rate)


async def current_vat_rate(db: AsyncSession) -> Decimal:
    """The team's VAT rate setting today. Read only: a missing settings row means the
    default it would be created with (creating it here would commit the caller's work)."""
    team = await TeamCRUD(db).get_first()
    settings = await TeamSettingsCRUD(db).get_by_team_id(team.id) if team else None
    return settings.vat_rate if settings is not None else DEFAULT_VAT_RATE
