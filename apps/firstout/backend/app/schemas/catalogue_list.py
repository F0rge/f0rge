"""Managed catalogue lists: categories (with sub-categories) and materials."""

from __future__ import annotations

import uuid
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, ConfigDict, StringConstraints

ListName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]
# Kept equal to ``app.models.catalogue_list.MATERIAL_FAMILIES`` (asserted by a test).
MaterialFamily = Literal["fabric", "leather", "wood", "stone", "metal", "glass", "woven", "other"]
Lifecycle = Literal["active", "archived", "all"]


class SalesAccount(BaseModel):
    code: str
    name: str


class ShopSection(BaseModel):
    slug: str
    label: str


class CategoryCreate(BaseModel):
    name: ListName
    # Set to create a sub-category of this (active, top-level) category.
    parent_id: Optional[uuid.UUID] = None
    shop_category: Optional[str] = None


class CategoryUpdate(BaseModel):
    """Fields left out are unchanged; ``shop_category: null`` clears the shop section."""

    name: Optional[ListName] = None
    is_archived: Optional[bool] = None
    shop_category: Optional[str] = None
    # Accepted only to refuse a move clearly: a category's level and parent are fixed.
    parent_id: Optional[uuid.UUID] = None


class CategoryResponse(BaseModel):
    id: uuid.UUID
    name: str
    parent_id: Optional[uuid.UUID]
    is_archived: bool
    # Top-level only; always null on a sub-category.
    shop_category: Optional[str]
    # Where sales post: the category's ledger map. A sub-category posts with its parent.
    sales_account: Optional[SalesAccount]
    # Active SKUs using this category (top-level) or sub-category.
    sku_count: int
    subcategories: list[CategoryResponse] = []


class CategoryTree(BaseModel):
    categories: list[CategoryResponse]
    shop_sections: list[ShopSection]


class MaterialCreate(BaseModel):
    name: ListName
    family: MaterialFamily


class MaterialUpdate(BaseModel):
    name: Optional[ListName] = None
    family: Optional[MaterialFamily] = None
    is_archived: Optional[bool] = None


class MaterialResponse(BaseModel):
    id: uuid.UUID
    name: str
    family: MaterialFamily
    is_archived: bool
    # Active SKUs carrying it as main or other material.
    sku_count: int

    model_config = ConfigDict(from_attributes=True)
