from __future__ import annotations

import enum
import uuid

from typing import Optional

from sqlalchemy import Boolean, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import CITEXT, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from f0rge_db.mixins import TimestampMixin, UUIDPkMixin


class UserRole(str, enum.Enum):
    OWNER = "owner"
    BUYER = "buyer"
    WAREHOUSE = "warehouse"
    TILL = "till"
    BOOKS = "books"


class User(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "users"

    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("teams.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(CITEXT, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    display_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    role: Mapped[UserRole] = mapped_column(
        Enum(
            UserRole,
            name="user_role",
            native_enum=False,
            length=32,
            values_callable=lambda members: [member.value for member in members],
        ),
        nullable=False,
    )
    is_disabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    default_location_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    team: Mapped["Team"] = relationship(back_populates="users")


from app.models.team import Team  # noqa: E402
