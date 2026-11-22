from __future__ import annotations

from typing import Optional

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from f0rge_db.mixins import TimestampMixin, UUIDPkMixin

if TYPE_CHECKING:
    from app.models.user import User


class Team(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "teams"

    slug: Mapped[str] = mapped_column(String(63), unique=True, nullable=False, default="firstout")
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="active", server_default="active"
    )
    clerk_org_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    storefront_curated_catalogue: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )

    users: Mapped[list[User]] = relationship(back_populates="team")
