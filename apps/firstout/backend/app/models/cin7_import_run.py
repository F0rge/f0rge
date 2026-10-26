from __future__ import annotations

import datetime
import uuid
from typing import Optional

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from f0rge_db.mixins import TimestampMixin, UUIDPkMixin


class Cin7ImportRun(UUIDPkMixin, TimestampMixin, Base):
    """Audit log and job row for an admin Cin7 import.

    ``active_lock`` is true only while the run is queued or running. Postgres
    allows many nulls in a unique index, so a single true value is the
    one-job-at-a-time lock.
    """

    __tablename__ = "cin7_import_runs"
    __table_args__ = (
        CheckConstraint(
            "mode IN ('dry_run', 'commit')",
            name="ck_cin7_import_runs_mode",
        ),
        CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed')",
            name="ck_cin7_import_runs_status",
        ),
        Index("ix_cin7_import_runs_created_at", "created_at"),
        Index("ix_cin7_import_runs_file_sha256", "file_sha256"),
        Index("uq_cin7_import_runs_one_active", "active_lock", unique=True),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    user_email: Mapped[str] = mapped_column(String(255), nullable=False)
    file_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    mode: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    dry_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cin7_import_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    finished_at: Mapped[Optional[datetime.datetime]] = mapped_column(nullable=True)
    summary: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    warnings: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    errors: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    warning_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    barcode_replacements: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    active_lock: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
