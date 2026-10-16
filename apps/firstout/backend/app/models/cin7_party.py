from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from f0rge_db.mixins import TimestampMixin, UUIDPkMixin


class _AddressColumns:
    """Postal address as Cin7 exports it. ``natural_key`` makes re-imports idempotent."""

    natural_key: Mapped[str] = mapped_column(String(64), nullable=False)
    address_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    line1: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    line2: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    state: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    postcode: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)


class _ContactColumns:
    natural_key: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    job_title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    mobile: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    fax: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    website: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    include_in_emails: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class CustomerAddress(_AddressColumns, UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "customer_addresses"

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    __table_args__ = (
        UniqueConstraint("customer_id", "natural_key", name="uq_customer_addresses_key"),
    )


class CustomerContact(_ContactColumns, UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "customer_contacts"

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    marketing_consent: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    __table_args__ = (
        UniqueConstraint("customer_id", "natural_key", name="uq_customer_contacts_key"),
    )


class SupplierAddress(_AddressColumns, UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "supplier_addresses"

    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("suppliers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    __table_args__ = (
        UniqueConstraint("supplier_id", "natural_key", name="uq_supplier_addresses_key"),
    )


class SupplierContact(_ContactColumns, UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "supplier_contacts"

    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("suppliers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    __table_args__ = (
        UniqueConstraint("supplier_id", "natural_key", name="uq_supplier_contacts_key"),
    )
