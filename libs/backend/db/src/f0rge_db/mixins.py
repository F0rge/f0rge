from __future__ import annotations

import datetime
import uuid

from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column


class UUIDPkMixin:
    """UUID primary key with a client-side uuid4 default. For NEW models."""

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )


class TimestampMixin:
    """created_at/updated_at, matching the column shape marrow models use
    (client-side ``datetime.utcnow`` default, ``onupdate`` refresh). For NEW
    models — existing marrow models were NOT retrofitted; see PR notes.
    """

    created_at: Mapped[datetime.datetime] = mapped_column(
        default=datetime.datetime.utcnow,
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
    )
