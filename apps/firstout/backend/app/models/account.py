from __future__ import annotations

import enum

from sqlalchemy import Boolean, CheckConstraint, Enum, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from f0rge_db.mixins import TimestampMixin, UUIDPkMixin


class AccountType(str, enum.Enum):
    ASSET = "asset"
    LIABILITY = "liability"
    EQUITY = "equity"
    INCOME = "income"
    EXPENSE = "expense"


class TaxTreatment(str, enum.Enum):
    NONE = "none"
    VAT15 = "vat15"


def default_tax_treatment(account_type: AccountType) -> TaxTreatment:
    if account_type in (AccountType.INCOME, AccountType.EXPENSE):
        return TaxTreatment.VAT15
    return TaxTreatment.NONE


class Account(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "accounts"

    code: Mapped[str] = mapped_column(String(16), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[AccountType] = mapped_column(
        Enum(
            AccountType,
            name="account_type",
            native_enum=False,
            length=32,
            values_callable=lambda members: [member.value for member in members],
        ),
        nullable=False,
    )
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_bank: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    tax_treatment: Mapped[TaxTreatment] = mapped_column(
        Enum(
            TaxTreatment,
            name="tax_treatment",
            native_enum=False,
            length=16,
            values_callable=lambda members: [member.value for member in members],
        ),
        nullable=False,
        default=TaxTreatment.NONE,
        server_default="none",
    )

    __table_args__ = (
        UniqueConstraint("code", name="uq_accounts_code"),
        CheckConstraint(
            "type IN ('asset', 'liability', 'equity', 'income', 'expense')",
            name="ck_accounts_type",
        ),
        CheckConstraint(
            "tax_treatment IN ('none', 'vat15')",
            name="ck_accounts_tax_treatment",
        ),
    )
