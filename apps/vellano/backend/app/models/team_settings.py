from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from f0rge_db.mixins import TimestampMixin, UUIDPkMixin

DEFAULT_VAT_RATE = Decimal("0.15")
DEFAULT_HOME_CURRENCY = "ZAR"
DEFAULT_NIA_MONTHLY_TOKEN_CAP = 500000


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

    team: Mapped["Team"] = relationship()

    __table_args__ = (UniqueConstraint("team_id", name="uq_team_settings_team_id"),)


from app.models.team import Team  # noqa: E402
