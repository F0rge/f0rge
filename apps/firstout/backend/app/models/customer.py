from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, Computed, ForeignKey, Index, Integer, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from f0rge_db.mixins import TimestampMixin, UUIDPkMixin

# Stored national digits: drop 0027 / a full 27 prefix, then one leading 0.
# Search and duplicate checks compare this form. Keep in sync with
# ``national_phone_digits`` in app.services.customer_match.
PHONE_NATIONAL_SQL = (
    "CASE WHEN phone IS NULL OR btrim(phone) = '' THEN NULL ELSE NULLIF("
    "regexp_replace(CASE "
    "WHEN left(regexp_replace(phone, '[^0-9]', '', 'g'), 4) = '0027' "
    "THEN substring(regexp_replace(phone, '[^0-9]', '', 'g') FROM 5) "
    "WHEN left(regexp_replace(phone, '[^0-9]', '', 'g'), 2) = '27' "
    "AND length(regexp_replace(phone, '[^0-9]', '', 'g')) >= 11 "
    "THEN substring(regexp_replace(phone, '[^0-9]', '', 'g') FROM 3) "
    "ELSE regexp_replace(phone, '[^0-9]', '', 'g') "
    "END, '^0', ''), '') END"
)


class Customer(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "customers"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    phone_national: Mapped[Optional[str]] = mapped_column(
        String(32),
        Computed(PHONE_NATIONAL_SQL, persisted=True),
        nullable=True,
    )
    vat_number: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    billing_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    customer_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="retail",
        server_default="retail",
    )
    price_tier: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="standard",
        server_default="standard",
    )
    credit_limit: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)
    on_hold: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    on_hold_reason: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    payment_terms_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    payment_reminders_opt_out: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    price_list_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("price_lists.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    __table_args__ = (
        Index("ix_customers_name_lower", text("lower(name)"), unique=True),
        Index(
            "ix_customers_name_trgm",
            "name",
            postgresql_using="gin",
            postgresql_ops={"name": "gin_trgm_ops"},
        ),
        Index(
            "ix_customers_email_trgm",
            "email",
            postgresql_using="gin",
            postgresql_ops={"email": "gin_trgm_ops"},
        ),
        Index(
            "ix_customers_phone_national_trgm",
            "phone_national",
            postgresql_using="gin",
            postgresql_ops={"phone_national": "gin_trgm_ops"},
        ),
    )
