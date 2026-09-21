from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from f0rge_db.mixins import TimestampMixin, UUIDPkMixin

DEFAULT_VAT_RATE = Decimal("0.15")
DEFAULT_HOME_CURRENCY = "ZAR"
DEFAULT_NIA_MONTHLY_TOKEN_CAP = 500000
DEFAULT_LEGAL_NAME = "Firstout"
DEFAULT_ADDRESS = "Kramerville, Johannesburg, South Africa"
DEFAULT_VAT_NUMBER = "4123456789"
DEFAULT_PAYMENT_TERMS_DAYS = 30
DEFAULT_SESSION_TTL_HOURS = 12


class TeamSettings(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "team_settings"

    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=False,
    )
    vat_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 4),
        nullable=False,
        default=DEFAULT_VAT_RATE,
    )
    home_currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default=DEFAULT_HOME_CURRENCY,
    )
    always_prefer_warehouse: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )
    pick_priority: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    nia_monthly_token_cap: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=DEFAULT_NIA_MONTHLY_TOKEN_CAP,
        server_default=text("500000"),
    )
    legal_name: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default=DEFAULT_LEGAL_NAME,
        server_default=text("'Firstout'"),
    )
    trading_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    address: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default=DEFAULT_ADDRESS,
        server_default=text("'Kramerville, Johannesburg, South Africa'"),
    )
    vat_number: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default=DEFAULT_VAT_NUMBER,
        server_default=text("'4123456789'"),
    )
    cipc_number: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    bank_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    bank_account: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    bank_branch_code: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    payment_terms_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=DEFAULT_PAYMENT_TERMS_DAYS,
        server_default=text("30"),
    )
    default_receive_location_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="SET NULL"),
        nullable=True,
    )
    default_till_location_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="SET NULL"),
        nullable=True,
    )
    logo_storage_key: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    max_till_discount_percent: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )
    po_approval_threshold_zar: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(14, 2),
        nullable=True,
    )
    session_ttl_hours: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=DEFAULT_SESSION_TTL_HOURS,
        server_default=text("12"),
    )
    smtp_host: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    smtp_port: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    smtp_security: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="starttls",
        server_default=text("'starttls'"),
    )
    smtp_username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    smtp_password_encrypted: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)
    smtp_from_address: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    smtp_from_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    smtp_reply_to: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    wa_phone_number_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    wa_business_account_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    wa_access_token_encrypted: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)
    wa_app_secret_encrypted: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)
    wa_invoice_template_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    wa_template_lang: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="en",
        server_default=text("'en'"),
    )

    team: Mapped["Team"] = relationship()
    default_receive_location: Mapped[Optional["Location"]] = relationship(
        foreign_keys=[default_receive_location_id],
    )
    default_till_location: Mapped[Optional["Location"]] = relationship(
        foreign_keys=[default_till_location_id],
    )

    __table_args__ = (
        UniqueConstraint("team_id", name="uq_team_settings_team_id"),
        CheckConstraint(
            "session_ttl_hours >= 1 AND session_ttl_hours <= 720",
            name="ck_team_settings_session_ttl_hours",
        ),
        CheckConstraint(
            "smtp_port IS NULL OR (smtp_port >= 1 AND smtp_port <= 65535)",
            name="ck_team_settings_smtp_port",
        ),
        CheckConstraint(
            "smtp_security IN ('starttls', 'ssl', 'plain')",
            name="ck_team_settings_smtp_security",
        ),
    )


from app.models.location import Location  # noqa: E402
from app.models.team import Team  # noqa: E402
