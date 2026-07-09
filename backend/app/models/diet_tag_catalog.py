from __future__ import annotations

import datetime
import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.user import default_user_id


class DietTagCatalogItem(Base):
    __tablename__ = "diet_tag_catalog"
    __table_args__ = (UniqueConstraint("user_id", "key", name="uq_diet_tag_catalog_user_id_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        default=default_user_id,
    )
    key: Mapped[str] = mapped_column(String, nullable=False, index=True)
    label: Mapped[str] = mapped_column(String, nullable=False)
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
    )
