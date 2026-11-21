from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.tenant import TenantOwnedMixin
from f0rge_db.mixins import TimestampMixin, UUIDPkMixin

DEFAULT_VAT_RATE = Decimal("0.15")
DEFAULT_HOME_CURRENCY = "ZAR"
DEFAULT_LEGAL_NAME = "Firstout"
DEFAULT_ADDRESS = "Kramerville, Johannesburg, South Africa"
DEFAULT_VAT_NUMBER = "4123456789"
DEFAULT_PAYMENT_TERMS_DAYS = 30
DEFAULT_SESSION_TTL_HOURS = 12
DEFAULT_TILL_HOLD_HOURS = 3


class TeamSettings(TenantOwnedMixin, UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "team_settings"

    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=False,
    )
    label_width_mm: Mapped[int] = mapped_column(
        Integer, nullable=False, default=100, server_default="100"
    )
    label_height_mm: Mapped[int] = mapped_column(
        Integer, nullable=False, default=60, server_default="60"
    )
    label_show_name: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    label_show_reference: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    label_show_barcode: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    label_show_logo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
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
    # Validated by app.schemas.document_template.DocumentTemplate; null prints the default.
    document_template: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
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
    till_hold_hours: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=DEFAULT_TILL_HOLD_HOURS,
        server_default=text("3"),
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
            "till_hold_hours >= 1 AND till_hold_hours <= 24",
            name="ck_team_settings_till_hold_hours",
        ),
    )


from app.models.location import Location  # noqa: E402
from app.models.team import Team  # noqa: E402
