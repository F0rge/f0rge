"""Managed catalogue lists: categories with one level of sub-categories, and materials.

Nothing else creates a category or a material: these services and migration 120 only.
"""

from __future__ import annotations

import datetime
import unicodedata
import uuid
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.catalogue_list import MaterialCRUD, SkuCategoryCRUD
from app.crud.category_account_map import CategoryAccountMapCRUD
from app.crud.ops_commerce import SHOP_CATEGORIES
from app.models.catalogue_list import MATERIAL_FAMILIES, Material, SkuCategory
from app.schemas.catalogue_list import (
    CategoryCreate,
    CategoryResponse,
    CategoryTree,
    CategoryUpdate,
    Lifecycle,
    MaterialCreate,
    MaterialResponse,
    MaterialUpdate,
    SalesAccount,
    ShopSection,
)
from f0rge_core.exceptions import ConflictError, NotFoundError, ValidationError
from f0rge_db.crud import unit_of_work

# Display names as the storefront shows them (commerce/src/catalogue-collections.ts).
SHOP_SECTION_LABELS = {
    "sofas-armchairs": "Sofas & Armchairs",
    "dining-room": "Dining Room",
    "bedroom": "Bedroom",
    "coffee-console-tables": "Coffee & Console Tables",
}


def fold_name(name: str) -> str:
    """Case- and accent-insensitive key: "Boucle" and "Bouclé" are the same name."""
    decomposed = unicodedata.normalize("NFKD", name.strip().casefold())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def shop_sections() -> list[ShopSection]:
    slugs = sorted(set(SHOP_CATEGORIES.values()))
    return [
        ShopSection(slug=slug, label=SHOP_SECTION_LABELS.get(slug, slug.replace("-", " ").title()))
        for slug in slugs
    ]


def _now() -> datetime.datetime:
    return datetime.datetime.utcnow()


def _skus(count: int) -> str:
    return f"{count} active SKU{'' if count == 1 else 's'}"


def _in_lifecycle(is_archived: bool, lifecycle: Lifecycle) -> bool:
    return lifecycle == "all" or is_archived == (lifecycle == "archived")


def _order(row: SkuCategory | Material) -> tuple[bool, str]:
    return (row.is_archived, fold_name(row.name))


class CategoryService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = SkuCategoryCRUD(db)
        self.map_crud = CategoryAccountMapCRUD(db)

    async def tree(self, lifecycle: Lifecycle = "active") -> CategoryTree:
        """Top-level categories with their sub-categories, active rows first.

        ``archived`` keeps an active category when it has archived sub-categories, so every
        archived sub-category is shown under its parent.
        """
        rows = await self.crud.list_all()
        counts = await self.crud.active_sku_counts()
        accounts = await self.crud.sales_accounts_by_category()
        children: dict[uuid.UUID, list[SkuCategory]] = {}
        for row in rows:
            if row.parent_id is not None:
                children.setdefault(row.parent_id, []).append(row)
        nodes = []
        for top in sorted((row for row in rows if row.parent_id is None), key=_order):
            subs = [
                sub
                for sub in sorted(children.get(top.id, []), key=_order)
                if _in_lifecycle(sub.is_archived, lifecycle)
            ]
            if _in_lifecycle(top.is_archived, lifecycle) or subs:
                nodes.append(self._node(top, subs, counts, accounts))
        return CategoryTree(categories=nodes, shop_sections=shop_sections())

    async def create(self, data: CategoryCreate) -> CategoryResponse:
        if data.parent_id is not None:
            parent = await self._get(data.parent_id)
            if parent.parent_id is not None:
                raise ConflictError(
                    f"'{parent.name}' is a sub-category; sub-categories cannot have their own."
                )
            if parent.is_archived:
                raise ConflictError(f"'{parent.name}' is archived. Restore it first.")
        shop_category = self._shop_category(data.shop_category, data.parent_id)
        await self._ensure_free(data.name, data.parent_id)
        category = SkuCategory(
            name=data.name, parent_id=data.parent_id, shop_category=shop_category
        )
        try:
            async with unit_of_work(self.db):
                await self.crud.add_and_flush(category)
        except IntegrityError as exc:
            raise ConflictError(self._taken(data.name, data.parent_id)) from exc
        return await self._response(category.id)

    async def update(self, category_id: uuid.UUID, data: CategoryUpdate) -> CategoryResponse:
        category = await self._get(category_id)
        fields = data.model_fields_set
        if "parent_id" in fields and data.parent_id != category.parent_id:
            raise ConflictError(
                "A category cannot move to another level or parent. "
                "Add a new sub-category under the right category instead."
            )
        if "shop_category" in fields:
            shop_category = self._shop_category(data.shop_category, category.parent_id)
        now = _now()
        renamed = data.name is not None and data.name != category.name
        archived = data.is_archived if data.is_archived is not None else category.is_archived
        if renamed and not archived:
            await self._ensure_free(data.name, category.parent_id, category.id)
        try:
            async with unit_of_work(self.db):
                if renamed:
                    if category.parent_id is None:
                        await self._cascade_rename(category.id, category.name, data.name)
                    category.name = data.name
                if data.is_archived is True and not category.is_archived:
                    await self._archive(category, now)
                elif data.is_archived is False and category.is_archived:
                    await self._restore(category)
                if "shop_category" in fields and shop_category != category.shop_category:
                    category.shop_category = shop_category
                    await self.crud.touch_skus(category.id, now)
                await self.crud.flush()
        except IntegrityError as exc:
            raise ConflictError(self._taken(category.name, category.parent_id)) from exc
        return await self._response(category.id)

    async def _archive(self, category: SkuCategory, now: datetime.datetime) -> None:
        in_use = await self.crud.active_sku_count(category)
        if in_use:
            kind = "category" if category.parent_id is None else "sub-category"
            raise ConflictError(
                f"{_skus(in_use)} use this {kind}. Move them to another {kind} first."
            )
        # Its sub-categories are unused here: every SKU in one is also in this category.
        if category.parent_id is None:
            await self.crud.archive_active_children(category.id, now)
        category.is_archived = True
        category.archived_at = now

    async def _restore(self, category: SkuCategory) -> None:
        if category.parent_id is not None:
            parent = await self._get(category.parent_id)
            if parent.is_archived:
                raise ConflictError(f"'{parent.name}' is archived. Restore it first.")
        await self._ensure_free(category.name, category.parent_id, category.id)
        category.is_archived = False
        category.archived_at = None

    async def _cascade_rename(self, category_id: uuid.UUID, old: str, new: str) -> None:
        """skus.category and the ledger map follow the name in the same transaction."""
        await self.crud.rename_sku_read_model(category_id, new)
        target = await self.map_crud.get_by_category_insensitive(new)
        mapping = await self.map_crud.get_by_category_insensitive(old)
        if target is not None and target is not mapping:
            raise ConflictError(
                f"Category posting already has an entry named '{target.category}'. "
                "Rename or remove that entry first."
            )
        if mapping is not None:
            mapping.category = new

    async def _ensure_free(
        self, name: str, parent_id: Optional[uuid.UUID], exclude_id: Optional[uuid.UUID] = None
    ) -> None:
        key = fold_name(name)
        if any(
            fold_name(other) == key for other in await self.crud.active_names(parent_id, exclude_id)
        ):
            raise ConflictError(self._taken(name, parent_id))

    @staticmethod
    def _taken(name: str, parent_id: Optional[uuid.UUID]) -> str:
        level = "category" if parent_id is None else "sub-category in this category"
        return f"An active {level} is already called '{name}'."

    @staticmethod
    def _shop_category(value: Optional[str], parent_id: Optional[uuid.UUID]) -> Optional[str]:
        if value is None:
            return None
        if parent_id is not None:
            raise ValidationError("Only a top-level category can have a shop section.")
        if value not in SHOP_CATEGORIES.values():
            raise ValidationError(f"Unknown shop section '{value}'.")
        return value

    async def _get(self, category_id: uuid.UUID) -> SkuCategory:
        category = await self.crud.get_by_id(category_id)
        if category is None:
            raise NotFoundError("Category not found")
        return category

    async def _response(self, category_id: uuid.UUID) -> CategoryResponse:
        category = await self._get(category_id)
        tree = await self.tree("all")
        for top in tree.categories:
            if top.id == category.id:
                return top
            for sub in top.subcategories:
                if sub.id == category.id:
                    return sub
        raise NotFoundError("Category not found")  # pragma: no cover - tree("all") has every row

    @staticmethod
    def _node(
        top: SkuCategory,
        subs: list[SkuCategory],
        counts: dict[uuid.UUID, int],
        accounts: dict[str, tuple[str, str]],
    ) -> CategoryResponse:
        mapped = accounts.get(top.name.strip().lower())
        account = SalesAccount(code=mapped[0], name=mapped[1]) if mapped else None
        return CategoryResponse(
            id=top.id,
            name=top.name,
            parent_id=None,
            is_archived=top.is_archived,
            shop_category=top.shop_category,
            sales_account=account,
            sku_count=counts.get(top.id, 0),
            subcategories=[
                CategoryResponse(
                    id=sub.id,
                    name=sub.name,
                    parent_id=top.id,
                    is_archived=sub.is_archived,
                    shop_category=None,
                    sales_account=account,
                    sku_count=counts.get(sub.id, 0),
                )
                for sub in subs
            ],
        )


class MaterialService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = MaterialCRUD(db)

    async def list(self, lifecycle: Lifecycle = "active") -> list[MaterialResponse]:
        counts = await self.crud.active_sku_counts()
        rows = [
            row for row in await self.crud.list_all() if _in_lifecycle(row.is_archived, lifecycle)
        ]
        rows.sort(
            key=lambda row: (
                row.is_archived,
                MATERIAL_FAMILIES.index(row.family),
                fold_name(row.name),
            )
        )
        return [self._response(row, counts) for row in rows]

    async def create(self, data: MaterialCreate) -> MaterialResponse:
        await self._ensure_free(data.name)
        material = Material(name=data.name, family=data.family)
        try:
            async with unit_of_work(self.db):
                await self.crud.add_and_flush(material)
        except IntegrityError as exc:
            raise ConflictError(self._taken(data.name)) from exc
        return await self._reloaded(material.id)

    async def update(self, material_id: uuid.UUID, data: MaterialUpdate) -> MaterialResponse:
        """Archiving is always allowed: SKUs keep the material, it just cannot be newly picked."""
        material = await self._get(material_id)
        name = data.name if data.name is not None else material.name
        archived = data.is_archived if data.is_archived is not None else material.is_archived
        if not archived and (name != material.name or material.is_archived):
            await self._ensure_free(name, material.id)
        if archived != material.is_archived:
            material.is_archived = archived
            material.archived_at = _now() if archived else None
        material.name = name
        if data.family is not None:
            material.family = data.family
        try:
            await self.crud.commit_refresh(material)
        except IntegrityError as exc:
            raise ConflictError(self._taken(material.name)) from exc
        return await self._reloaded(material.id)

    async def _ensure_free(self, name: str, exclude_id: Optional[uuid.UUID] = None) -> None:
        key = fold_name(name)
        if any(fold_name(other) == key for other in await self.crud.active_names(exclude_id)):
            raise ConflictError(self._taken(name))

    @staticmethod
    def _taken(name: str) -> str:
        return f"An active material is already called '{name}'."

    async def _get(self, material_id: uuid.UUID) -> Material:
        material = await self.crud.get_by_id(material_id)
        if material is None:
            raise NotFoundError("Material not found")
        return material

    async def _reloaded(self, material_id: uuid.UUID) -> MaterialResponse:
        return self._response(await self._get(material_id), await self.crud.active_sku_counts())

    @staticmethod
    def _response(row: Material, counts: dict[uuid.UUID, int]) -> MaterialResponse:
        return MaterialResponse(
            id=row.id,
            name=row.name,
            family=row.family,
            is_archived=row.is_archived,
            sku_count=counts.get(row.id, 0),
        )
