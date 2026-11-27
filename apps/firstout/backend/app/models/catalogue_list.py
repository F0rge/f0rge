"""Managed catalogue lists: categories with one level of sub-categories, and materials."""

from __future__ import annotations

import datetime
import uuid
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    SmallInteger,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.tenant import TenantOwnedMixin
from f0rge_db.mixins import TimestampMixin, UUIDPkMixin

MATERIAL_FAMILIES = ("fabric", "leather", "wood", "stone", "metal", "glass", "woven", "other")

# Seeded for every tenant: by migration 120 for existing teams, by tenant signup for new ones.
# The seven default categories are the names in ``chart_of_accounts.CATEGORY_MAPS``.
DEFAULT_MATERIALS: tuple[tuple[str, str], ...] = (
    ("Bouclé", "fabric"),
    ("Velvet", "fabric"),
    ("Linen", "fabric"),
    ("Wool", "fabric"),
    ("Leather", "leather"),
    ("Oak", "wood"),
    ("Ash", "wood"),
    ("Teak", "wood"),
    ("Beech", "wood"),
    ("Walnut", "wood"),
    ("Pine", "wood"),
    ("Travertine", "stone"),
    ("Marble", "stone"),
    ("Brass", "metal"),
    ("Steel", "metal"),
    ("Aluminium", "metal"),
    ("Glass", "glass"),
    ("Rattan", "woven"),
)


class SkuCategory(TenantOwnedMixin, UUIDPkMixin, TimestampMixin, Base):
    """A category (``parent_id`` null) or a sub-category of exactly one category.

    Two levels only: the service refuses a parent that has a parent itself.
    """

    __tablename__ = "sku_categories"

    name: Mapped[str] = mapped_column(String(64), nullable=False)
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    # A shop section slug (a value of ops_commerce.SHOP_CATEGORIES); top-level rows only.
    shop_category: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    is_archived: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    archived_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("team_id", "id", name="uq_sku_categories_team_id_id"),
        # Target of skus' sub-category key, which also pins the sub-category's parent.
        UniqueConstraint("team_id", "id", "parent_id", name="uq_sku_categories_team_id_id_parent"),
        ForeignKeyConstraint(
            ["team_id", "parent_id"],
            ["sku_categories.team_id", "sku_categories.id"],
            name="fk_sku_categories_parent_tenant",
            ondelete="RESTRICT",
        ),
        Index(
            "ix_sku_categories_top_name_active_lower",
            text("lower(name)"),
            unique=True,
            postgresql_where=text("parent_id IS NULL AND NOT is_archived"),
        ),
        Index(
            "ix_sku_categories_sub_name_active_lower",
            "parent_id",
            text("lower(name)"),
            unique=True,
            postgresql_where=text("parent_id IS NOT NULL AND NOT is_archived"),
        ),
        CheckConstraint("parent_id <> id", name="ck_sku_categories_not_own_parent"),
        CheckConstraint(
            "shop_category IS NULL OR parent_id IS NULL", name="ck_sku_categories_shop_top_level"
        ),
    )


class Material(TenantOwnedMixin, UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "materials"

    name: Mapped[str] = mapped_column(String(64), nullable=False)
    family: Mapped[str] = mapped_column(String(16), nullable=False)
    is_archived: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    archived_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("team_id", "id", name="uq_materials_team_id_id"),
        Index(
            "ix_materials_name_active_lower",
            text("lower(name)"),
            unique=True,
            postgresql_where=text("NOT is_archived"),
        ),
        CheckConstraint(
            "family IN ('fabric', 'leather', 'wood', 'stone', 'metal', 'glass', 'woven', 'other')",
            name="ck_materials_family",
        ),
    )


class SkuMaterial(TenantOwnedMixin, UUIDPkMixin, TimestampMixin, Base):
    """One of a SKU's other materials; the main material is ``skus.main_material_id``."""

    __tablename__ = "sku_materials"

    sku_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    material_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    material: Mapped[Material] = relationship(
        primaryjoin="SkuMaterial.material_id == Material.id",
        foreign_keys="[SkuMaterial.material_id]",
        viewonly=True,
    )

    __table_args__ = (
        UniqueConstraint("team_id", "id", name="uq_sku_materials_team_id_id"),
        UniqueConstraint("sku_id", "material_id", name="uq_sku_materials_sku_material"),
        ForeignKeyConstraint(
            ["team_id", "sku_id"],
            ["skus.team_id", "skus.id"],
            name="fk_sku_materials_sku_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["team_id", "material_id"],
            ["materials.team_id", "materials.id"],
            name="fk_sku_materials_material_tenant",
            ondelete="RESTRICT",
        ),
        # The unique key leads with sku_id; this serves lookups by material.
        Index("ix_sku_materials_material", "team_id", "material_id"),
        CheckConstraint("position >= 0", name="ck_sku_materials_position"),
    )
