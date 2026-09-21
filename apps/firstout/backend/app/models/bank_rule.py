from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from f0rge_db.mixins import TimestampMixin, UUIDPkMixin


class BankRule(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "bank_rules"

    bank_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    pattern: Mapped[str] = mapped_column(String(128), nullable=False)
    target_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    bank_account: Mapped["Account"] = relationship(
        foreign_keys=[bank_account_id],
        lazy="selectin",
    )
    target_account: Mapped["Account"] = relationship(
        foreign_keys=[target_account_id],
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint(
            "bank_account_id",
            "pattern",
            name="uq_bank_rules_bank_account_id_pattern",
        ),
    )


from app.models.account import Account  # noqa: E402
