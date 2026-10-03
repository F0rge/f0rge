from __future__ import annotations

import json
import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.product_group import ProductGroupCRUD
from app.models.product_group import ProductGroup
from app.schemas.product_group import (
    ProductGroupCreate,
    ProductGroupResponse,
    ProductGroupUpdate,
    ProductGroupVariantInput,
    ProductGroupVariantResponse,
)
from f0rge_core.exceptions import ConflictError, NotFoundError, ValidationError
from f0rge_db.crud import unit_of_work


class ProductGroupService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = ProductGroupCRUD(db)

    async def list(self) -> list[ProductGroupResponse]:
        return [await self._response(group) for group in await self.crud.list_groups()]

    async def get(self, group_id: uuid.UUID) -> ProductGroupResponse:
        return await self._response(await self._required(group_id))

    async def create(self, data: ProductGroupCreate) -> ProductGroupResponse:
        options = self._validate_options(data.options)
        if not data.title.strip():
            raise ValidationError("title must be non-empty")
        self._validate_selections(options, data.variants)
        try:
            async with unit_of_work(self.db):
                group = await self.crud.add_group(data.title.strip(), options)
                await self._replace(group, data.variants)
        except IntegrityError as exc:
            raise ConflictError("A SKU or option combination is already mapped") from exc
        return await self._response(group)

    async def update(self, group_id: uuid.UUID, data: ProductGroupUpdate) -> ProductGroupResponse:
        group = await self._required(group_id)
        options = (
            self._validate_options(data.options) if data.options is not None else group.options
        )
        existing = [
            ProductGroupVariantInput(source_sku_id=variant.source_sku_id, options=variant.options)
            for variant, _ in await self.crud.variants(group.id)
        ]
        self._validate_selections(options, existing)
        if data.storefront_published is True:
            await self._validate_publish(existing)
        async with unit_of_work(self.db):
            if "title" in data.model_fields_set:
                if data.title is None or not data.title.strip():
                    raise ValidationError("title must be non-empty")
                group.title = data.title.strip()
            if "options" in data.model_fields_set:
                group.options = options
            if "storefront_published" in data.model_fields_set:
                if data.storefront_published is None:
                    raise ValidationError("storefront_published must be true or false")
                group.storefront_published = data.storefront_published
            await self.db.flush()
        return await self._response(group)

    async def replace_variants(
        self, group_id: uuid.UUID, variants: list[ProductGroupVariantInput]
    ) -> ProductGroupResponse:
        group = await self._required(group_id)
        self._validate_selections(group.options, variants)
        if group.storefront_published:
            await self._validate_publish(variants)
        try:
            async with unit_of_work(self.db):
                await self._replace(group, variants)
        except IntegrityError as exc:
            raise ConflictError("A SKU or option combination is already mapped") from exc
        return await self._response(group)

    async def _required(self, group_id: uuid.UUID) -> ProductGroup:
        group = await self.crud.get_group(group_id)
        if group is None:
            raise NotFoundError("Product group not found")
        return group

    async def _response(self, group: ProductGroup) -> ProductGroupResponse:
        variants = await self.crud.variants(group.id)
        return ProductGroupResponse(
            id=group.id,
            title=group.title,
            options=group.options,
            storefront_published=group.storefront_published,
            variants=[
                ProductGroupVariantResponse(
                    source_sku_id=variant.source_sku_id,
                    sku=sku.our_ref,
                    name=sku.name,
                    options=variant.options,
                )
                for variant, sku in variants
            ],
            created_at=group.created_at,
            updated_at=group.updated_at,
        )

    @staticmethod
    def _validate_options(options: dict[str, list[str]]) -> dict[str, list[str]]:
        if not options:
            raise ValidationError("A product group needs at least one option")
        normalized: dict[str, list[str]] = {}
        normalized_names: set[str] = set()
        for raw_name, raw_values in options.items():
            name = raw_name.strip()
            values = [value.strip() for value in raw_values]
            if not name or not values or any(not value for value in values):
                raise ValidationError("Option names and values must be non-empty")
            normalized_name = name.casefold()
            if normalized_name in normalized_names or len(values) != len(set(values)):
                raise ConflictError("Option names and values must be unique")
            normalized_names.add(normalized_name)
            normalized[name] = values
        return normalized

    @staticmethod
    def _validate_selections(
        options: dict[str, list[str]], variants: list[ProductGroupVariantInput]
    ) -> None:
        sku_ids: set[uuid.UUID] = set()
        signatures: set[str] = set()
        for variant in variants:
            if set(variant.options) != set(options):
                raise ValidationError("Every variant must select every defined option")
            if any(value not in options[name] for name, value in variant.options.items()):
                raise ValidationError("Variant uses an undefined option value")
            signature = json.dumps(variant.options, sort_keys=True, separators=(",", ":"))
            if len(signature) > 2048:
                raise ValidationError("Variant option combination is too long")
            if variant.source_sku_id in sku_ids or signature in signatures:
                raise ConflictError("Duplicate SKU or option combination")
            sku_ids.add(variant.source_sku_id)
            signatures.add(signature)

    async def _replace(
        self,
        group: ProductGroup,
        variants: list[ProductGroupVariantInput],
    ) -> None:
        sku_ids = [variant.source_sku_id for variant in variants]
        skus = await self.crud.skus(sku_ids)
        if len(skus) != len(sku_ids):
            raise NotFoundError("SKU not found")
        if await self.crud.mapped_sku_ids(sku_ids, exclude_group_id=group.id):
            raise ConflictError("A SKU is already mapped to another product group")
        await self.crud.replace_variants(
            group.id,
            [
                (
                    variant.source_sku_id,
                    variant.options,
                    json.dumps(variant.options, sort_keys=True, separators=(",", ":")),
                )
                for variant in variants
            ],
        )

    async def _validate_publish(self, variants: list[ProductGroupVariantInput]) -> None:
        if len(variants) < 2:
            raise ValidationError("A published product group needs at least two variants")
        skus = await self.crud.skus([variant.source_sku_id for variant in variants])
        if len(skus) != len(variants):
            raise NotFoundError("SKU not found")
        if any(
            not sku.storefront_published or sku.retail_ex_vat is None or sku.retail_ex_vat <= 0
            for sku in skus.values()
        ):
            raise ValidationError("Publish each SKU with a positive retail price first")
