from __future__ import annotations

import datetime
import enum
import uuid
from typing import Any, Optional

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from f0rge_db.mixins import TimestampMixin, UUIDPkMixin


class Vat201PeriodStatus(str, enum.Enum):
    DRAFT = "draft"
    DUE = "due"
    LOCKED = "locked"


class Vat201PeriodEventAction(str, enum.Enum):
    LOCK = "lock"
    REOPEN = "reopen"


class Vat201Period(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "vat201_periods"

    period_from: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    period_to: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    status: Mapped[Vat201PeriodStatus] = mapped_column(
        Enum(
            Vat201PeriodStatus,
            name="vat201_period_status",
            native_enum=False,
            length=32,
            values_callable=lambda members: [member.value for member in members],
        ),
        nullable=False,
        default=Vat201PeriodStatus.DRAFT,
        server_default="draft",
    )
    snapshot_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    locked_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    locked_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    reopen_reason: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    events: Mapped[list["Vat201PeriodEvent"]] = relationship(
        back_populates="period",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="Vat201PeriodEvent.created_at",
    )

    __table_args__ = (
        UniqueConstraint(
            "period_from",
            "period_to",
            name="uq_vat201_periods_period_from_period_to",
        ),
        CheckConstraint(
            "status IN ('draft', 'due', 'locked')",
            name="ck_vat201_periods_status",
        ),
    )


class Vat201PeriodEvent(UUIDPkMixin, Base):
    __tablename__ = "vat201_period_events"

    period_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vat201_periods.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action: Mapped[Vat201PeriodEventAction] = mapped_column(
        Enum(
            Vat201PeriodEventAction,
            name="vat201_period_event_action",
            native_enum=False,
            length=32,
            values_callable=lambda members: [member.value for member in members],
        ),
        nullable=False,
    )
    snapshot_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    reason: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.datetime.utcnow,
    )

    period: Mapped["Vat201Period"] = relationship(back_populates="events")

    __table_args__ = (
        CheckConstraint(
            "action IN ('lock', 'reopen')",
            name="ck_vat201_period_events_action",
        ),
    )
