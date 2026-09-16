from __future__ import annotations

import datetime
import uuid
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import CITEXT, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from f0rge_db.mixins import TimestampMixin, UUIDPkMixin

TENANT_STATUS_PROVISIONING = "provisioning"
TENANT_STATUS_READY = "ready"
TENANT_STATUS_SUSPENDED = "suspended"
TENANT_STATUS_FAILED = "failed"

SIGNUP_STATUS_PENDING_VERIFY = "pending_verify"
SIGNUP_STATUS_VERIFIED = "verified"
SIGNUP_STATUS_PROVISIONING = "provisioning"
SIGNUP_STATUS_READY = "ready"
SIGNUP_STATUS_FAILED = "failed"
SIGNUP_STATUS_EXPIRED = "expired"


class PlatformBase(DeclarativeBase):
    pass


class Tenant(UUIDPkMixin, TimestampMixin, PlatformBase):
    __tablename__ = "tenants"
    __table_args__ = (UniqueConstraint("slug", name="uq_tenants_slug"),)

    slug: Mapped[str] = mapped_column(CITEXT, nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    database_url_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    storage_prefix: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    region: Mapped[str] = mapped_column(Text, nullable=False, default="railway-sfo")
    provisioned_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=False),
        nullable=True,
    )

    hostnames: Mapped[list[TenantHostname]] = relationship(back_populates="tenant")


class TenantHostname(UUIDPkMixin, TimestampMixin, PlatformBase):
    __tablename__ = "tenant_hostnames"
    __table_args__ = (UniqueConstraint("hostname", name="uq_tenant_hostnames_hostname"),)

    hostname: Mapped[str] = mapped_column(Text, nullable=False)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    tenant: Mapped[Tenant] = relationship(back_populates="hostnames")


class Signup(UUIDPkMixin, TimestampMixin, PlatformBase):
    __tablename__ = "signups"

    email: Mapped[str] = mapped_column(CITEXT, nullable=False, index=True)
    legal_name: Mapped[str] = mapped_column(String(200), nullable=False)
    trading_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    slug: Mapped[str] = mapped_column(CITEXT, nullable=False)
    owner_name: Mapped[str] = mapped_column(String(120), nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    verify_token_hash: Mapped[Optional[str]] = mapped_column(Text, unique=True, nullable=True)
    verify_expires_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=False),
        nullable=True,
    )
    verified_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=False),
        nullable=True,
    )
    privacy_version: Mapped[str] = mapped_column(Text, nullable=False)
    authorised_confirmed_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=False),
        nullable=True,
    )
    created_ip: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tenant_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    failure_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
