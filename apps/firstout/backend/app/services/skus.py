from __future__ import annotations

import asyncio
import datetime
import hashlib
import uuid
from decimal import ROUND_HALF_UP, Decimal
from pathlib import PurePosixPath
from typing import Optional, Union

from fastapi import UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import Response
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.location import LocationCRUD
from app.crud.sku import SkuCRUD
from app.crud.sku_bom_line import SkuBomLineCRUD
from app.crud.supplier import SupplierCRUD
from app.services.party_archive import assert_supplier_active
from app.crud.unit_cost_audit import UnitCostAuditCRUD
from app.models.catalogue_list import Material, SkuCategory, SkuMaterial
from app.models.sku import Sku
from app.models.unit_cost_audit import UnitCostAuditSource
from app.permissions import STOCK_COST_VIEW
from app.services.permissions import PermissionService
from app.schemas.sku import (
    SKU_DETAIL_FIELDS,
    SkuCreate,
    SkuListPage,
    SkuMaterialSummary,
    SkuPricePreviewChanges,
    SkuPricePreviewRequest,
    SkuPricePreviewResponse,
    SkuResponse,
    SkuUnitCostItem,
    SkuUnitCostPage,
    SkuUpdate,
)
from app.services.inventory import InventoryService
from app.services.pricing import resolve_classification_price
from app.services.sale_line_pricing import line_amounts
from app.services.sku_barcode import csv_style_barcode
from app.services.sku_classification import (
    DUPLICATE_FINISH_MESSAGE,
    FABRIC_PLACEHOLDER,
    categories_by_id,
    category_by_name,
    finish_label,
    materials_by_id,
    unknown_category_message,
)
from app.services.stock_movements import StockMovementService
from app.services.suspect_price import average_costs_by_sku_id, tier_price_below_cost
from app.services.vat import (
    CENT,
    current_vat_rate,
    inc_to_ex,
    inc_vat_or_none,
    retail_inc_to_ex,
    validate_non_negative_price,
)
from app.services.object_storage import (
    read_bytes,
    save_bytes,
)
from f0rge_core.exceptions import ConflictError, NotFoundError, ValidationError
from f0rge_db.crud import unit_of_work
from f0rge_db.organisation import tenant_id_ctx
from f0rge_storage.images import resize_image


# Stored ex VAT. Inc-VAT inputs convert at the team's current rate.
_PRICE_COLUMNS = (
    ("stockist_ex_vat", "stockist_ex_vat", "stockist_inc_vat"),
    ("wholesale_ex_vat", "wholesale_ex_vat", "wholesale_inc_vat"),
    ("decorator_ex_vat", "decorator_ex_vat", "decorator_inc_vat"),
    ("retail_ex_vat", "retail_ex_vat", "retail_inc_vat"),
)


def _sku_price_updates(
    data: Union[SkuUpdate, SkuPricePreviewChanges],
    vat_rate: Decimal,
) -> dict[str, Optional[Decimal]]:
    updates: dict[str, Optional[Decimal]] = {}
    fields_set = data.model_fields_set
    for column, ex_field, inc_field in _PRICE_COLUMNS:
        if ex_field in fields_set and inc_field in fields_set:
            raise ValidationError(f"Cannot set both {ex_field} and {inc_field}")
        if ex_field in fields_set:
            value = getattr(data, ex_field)
            if value is not None:
                validate_non_negative_price(value, ex_field)
                if column == "retail_ex_vat":
                    value = value.quantize(CENT, rounding=ROUND_HALF_UP)
            updates[column] = value
        elif inc_field in fields_set:
            value = getattr(data, inc_field)
            if value is not None:
                validate_non_negative_price(value, inc_field)
                convert = retail_inc_to_ex if column == "retail_ex_vat" else inc_to_ex
                value = convert(value, vat_rate)
            updates[column] = value
    return updates


def field_errors(errors: list[tuple[str, str]]) -> RequestValidationError:
    """A 422 in FastAPI's own shape, so clients attach each message to its field."""
    return RequestValidationError(
        [
            {
                "type": "value_error",
                # "rows.0.supplier_id" -> ("body", "rows", 0, "supplier_id")
                "loc": ("body", *(int(p) if p.isdigit() else p for p in field.split("."))),
                "msg": message,
                "input": None,
            }
            for field, message in errors
        ]
    )


def _blank_to_none(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


class SkuService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = SkuCRUD(db)
        self.location_crud = LocationCRUD(db)
        self.supplier_crud = SupplierCRUD(db)
        self.unit_cost_audit_crud = UnitCostAuditCRUD(db)
        self.bom_crud = SkuBomLineCRUD(db)
        self.stock_movements = StockMovementService(db)

    async def list(
        self,
        category: Optional[str] = None,
        user_id: Optional[uuid.UUID] = None,
        *,
        limit: Optional[int] = None,
        offset: int = 0,
        q: Optional[str] = None,
        preferred_supplier_id: Optional[uuid.UUID] = None,
        lifecycle: str = "active",
    ) -> Union[list[SkuResponse], SkuListPage]:
        category = _blank_to_none(category)
        q = _blank_to_none(q)
        if limit is None:
            skus = await self.crud.list_all(
                category=category,
                q=q,
                preferred_supplier_id=preferred_supplier_id,
                lifecycle=lifecycle,
            )
            return await self._to_responses(skus, user_id)
        skus, total = await self.crud.list_filtered(
            category=category,
            q=q,
            preferred_supplier_id=preferred_supplier_id,
            lifecycle=lifecycle,
            limit=limit,
            offset=offset,
        )
        return SkuListPage(
            items=await self._to_responses(skus, user_id),
            total=total,
            categories=await self.crud.list_categories(lifecycle=lifecycle),
        )

    async def list_unit_costs(
        self,
        user_id: Optional[uuid.UUID] = None,
        *,
        category: Optional[str] = None,
        q: Optional[str] = None,
        preferred_supplier_id: Optional[uuid.UUID] = None,
        lifecycle: str = "active",
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> SkuUnitCostPage:
        category = _blank_to_none(category)
        q = _blank_to_none(q)
        skus, total = await self.crud.list_filtered(
            category=category,
            q=q,
            preferred_supplier_id=preferred_supplier_id,
            lifecycle=lifecycle,
            limit=limit,
            offset=offset,
        )
        costs = await InventoryService(self.db).unit_costs_by_sku_id(
            [sku.id for sku in skus], user_id
        )
        return SkuUnitCostPage(
            items=[SkuUnitCostItem(sku_id=sku.id, unit_cost_zar=costs.get(sku.id)) for sku in skus],
            total=total,
        )

    async def get(self, sku_id: uuid.UUID, user_id: Optional[uuid.UUID] = None) -> SkuResponse:
        sku = await self.crud.get_by_id(sku_id)
        if sku is None:
            raise NotFoundError("SKU not found")
        return (await self._to_responses([sku], user_id))[0]

    async def price_preview(
        self, sku_id: uuid.UUID, data: SkuPricePreviewRequest
    ) -> SkuPricePreviewResponse:
        sku = await self.crud.get_by_id(sku_id)
        if sku is None:
            raise NotFoundError("SKU not found")
        vat_rate = await current_vat_rate(self.db)
        updates = _sku_price_updates(data.price_changes, vat_rate)
        retail = updates.get("retail_ex_vat")
        if retail is not None and retail.quantize(CENT, rounding=ROUND_HALF_UP) > Decimal(
            "9999999999.99"
        ):
            raise ValidationError("Retail price exceeds the maximum supported price")
        resolved = resolve_classification_price(sku, data.classification, price_updates=updates)
        unit = resolved.unit_ex_vat.quantize(CENT, rounding=ROUND_HALF_UP)
        subtotal, vat, total = line_amounts(unit, data.quantity, None, vat_rate)
        return SkuPricePreviewResponse(
            vat_rate=vat_rate,
            unit_ex_vat=unit,
            subtotal_ex_vat=subtotal,
            vat_amount=vat,
            total_inc_vat=total,
            source=resolved.source,
        )

    async def update(
        self, sku_id: uuid.UUID, data: SkuUpdate, user_id: Optional[uuid.UUID] = None
    ) -> SkuResponse:
        from app.services.sku_archive import SkuArchiveService

        await SkuArchiveService(self.db).lock_skus([sku_id])
        sku = await self.crud.get_by_id(sku_id)
        if sku is None:
            raise NotFoundError("SKU not found")
        if sku.is_archived:
            raise ConflictError("Restore the SKU before editing it")

        fields_set = data.model_fields_set

        if "is_sellable" in fields_set:
            if data.is_sellable is None:
                raise ValidationError("is_sellable must not be null")
            sku.is_sellable = data.is_sellable

        if "till_no_stock_required" in fields_set:
            if data.till_no_stock_required is None:
                raise ValidationError("till_no_stock_required must not be null")
            if data.till_no_stock_required and await self.bom_crud.list_by_parent(sku.id):
                raise ConflictError("Kits require stock at the till")
            sku.till_no_stock_required = data.till_no_stock_required

        if "exclude_from_commission" in fields_set:
            if data.exclude_from_commission is None:
                raise ValidationError("exclude_from_commission must not be null")
            sku.exclude_from_commission = data.exclude_from_commission

        if "storefront_hidden" in fields_set:
            if data.storefront_hidden is None:
                raise ValidationError("storefront_hidden must not be null")
            sku.storefront_hidden = data.storefront_hidden

        if "our_ref" in fields_set:
            assert data.our_ref is not None
            if await self.crud.get_by_our_ref(data.our_ref, exclude_id=sku.id) is not None:
                raise ConflictError("A SKU with this our_ref already exists")
            sku.our_ref = data.our_ref

        if "our_barcode" in fields_set:
            assert data.our_barcode is not None
            if await self.crud.get_by_our_barcode(data.our_barcode, exclude_id=sku.id) is not None:
                raise ConflictError("A SKU with this our_barcode already exists")
            sku.our_barcode = data.our_barcode

        if "name" in fields_set:
            assert data.name is not None
            sku.name = data.name

        if "design" in fields_set:
            assert data.design is not None
        other_materials = await self._apply_catalogue_fields(sku, data, fields_set)
        if other_materials is not None:
            await self._replace_other_materials(sku.id, other_materials)

        if "swatch_hex" in fields_set:
            sku.swatch_hex = data.swatch_hex

        if "preferred_supplier_id" in fields_set:
            if data.preferred_supplier_id is not None:
                supplier = await self.supplier_crud.get_by_id(data.preferred_supplier_id)
                if supplier is None:
                    raise NotFoundError("Supplier not found")
                if data.preferred_supplier_id != sku.preferred_supplier_id:
                    assert_supplier_active(supplier)
            sku.preferred_supplier_id = data.preferred_supplier_id

        if "lead_time_days" in fields_set:
            sku.lead_time_days = data.lead_time_days

        made_to_order_fields = {
            "made_to_order_capacity",
            "made_to_order_lead_time_min_days",
            "made_to_order_lead_time_max_days",
            "made_to_order_expires_at",
        }
        if made_to_order_fields.intersection(fields_set):
            offer = {
                field: getattr(data, field) if field in fields_set else getattr(sku, field)
                for field in made_to_order_fields
            }
            if all(value is None for value in offer.values()):
                sku.made_to_order_capacity = None
                sku.made_to_order_lead_time_min_days = None
                sku.made_to_order_lead_time_max_days = None
                sku.made_to_order_expires_at = None
                sku.made_to_order_offer_id = None
            else:
                capacity = offer["made_to_order_capacity"]
                lead_min = offer["made_to_order_lead_time_min_days"]
                lead_max = offer["made_to_order_lead_time_max_days"]
                expires_at = offer["made_to_order_expires_at"]
                if any(value is None for value in offer.values()):
                    raise ValidationError(
                        "Made-to-order capacity, lead-time range, and expiry must be set together"
                    )
                if lead_min > lead_max:
                    raise ValidationError(
                        "Made-to-order maximum lead time must be at least the minimum"
                    )
                if expires_at.tzinfo is None or expires_at.utcoffset() is None:
                    raise ValidationError("Made-to-order expiry must include a timezone")
                expires_at = expires_at.astimezone(datetime.timezone.utc)
                now = datetime.datetime.now(datetime.timezone.utc)
                if expires_at <= now:
                    raise ValidationError("Made-to-order expiry must be in the future")

                previous_expiry = sku.made_to_order_expires_at
                previous_expired = previous_expiry is not None and previous_expiry <= now
                if (
                    sku.made_to_order_capacity != capacity
                    or sku.made_to_order_offer_id is None
                    or previous_expired
                ):
                    # Editing the finite allowance starts a new allocation cycle.
                    # The Storefront retains earlier paid commitments by offer ID.
                    sku.made_to_order_offer_id = uuid.uuid4()
                sku.made_to_order_capacity = capacity
                sku.made_to_order_lead_time_min_days = lead_min
                sku.made_to_order_lead_time_max_days = lead_max
                sku.made_to_order_expires_at = expires_at

        if "supplier_ref" in fields_set:
            sku.supplier_ref = data.supplier_ref

        for field in SKU_DETAIL_FIELDS:
            if field in fields_set:
                setattr(sku, field, getattr(data, field))

        if "carton_count" in fields_set:
            assert data.carton_count is not None
            sku.carton_count = data.carton_count

        # Catalogue prices convert at the team's rate today (ADR 0003).
        vat_rate = await current_vat_rate(self.db)
        for column, amount in _sku_price_updates(data, vat_rate).items():
            setattr(sku, column, amount)

        try:
            await self.crud.commit_refresh(sku)
        except IntegrityError as exc:
            await self._raise_integrity_conflict(exc)
        reloaded = await self.crud.get_by_id(sku.id)
        assert reloaded is not None
        return (await self._to_responses([reloaded], user_id))[0]

    async def delete(self, sku_id: uuid.UUID) -> None:
        from app.services.sku_archive import SkuArchiveService

        await SkuArchiveService(self.db).lock_skus([sku_id])
        sku = await self.crud.get_by_id(sku_id)
        if sku is None:
            raise NotFoundError("SKU not found")
        if sku.is_archived:
            raise ConflictError(
                "Archived SKUs are retained with their history; restore the SKU instead"
            )
        try:
            await self.crud.delete_and_commit(sku)
        except IntegrityError as exc:
            raise ConflictError(
                "Cannot delete a SKU that has stock, orders, or sales history."
            ) from exc

    async def create(self, data: SkuCreate, user_id: uuid.UUID) -> SkuResponse:
        barcode = data.our_barcode
        if barcode is None:
            barcode = await self._allocate_csv_barcode(data.our_ref)
        await self._ensure_unique_fields(data.our_ref, barcode)

        if data.opening_location_id is not None:
            location = await self.location_crud.get_by_id(data.opening_location_id)
            if location is None:
                raise NotFoundError("Location not found")
            if location.is_archived:
                raise ConflictError("Cannot set opening stock at archived location")

        sku = Sku(
            is_sellable=data.is_sellable,
            till_no_stock_required=data.till_no_stock_required,
            exclude_from_commission=data.exclude_from_commission,
            our_ref=data.our_ref,
            our_barcode=barcode,
            name=data.name,
            supplier_ref=data.supplier_ref,
            swatch_hex=data.swatch_hex,
            carton_count=data.carton_count,
            **{field: getattr(data, field) for field in SKU_DETAIL_FIELDS},
        )
        # Every catalogue field counts as sent on create, defaults included.
        # The deprecated inputs, and an omitted minimum, count only when actually sent.
        only_when_sent = {"min_sell_qty", "fabric", "category"}
        create_fields = set(type(data).model_fields) - only_when_sent
        create_fields |= data.model_fields_set & only_when_sent
        other_materials = await self._apply_catalogue_fields(sku, data, create_fields)
        try:
            async with unit_of_work(self.db):
                await self.crud.add_and_flush(sku)
                if other_materials:
                    await self._replace_other_materials(sku.id, other_materials)
                if data.opening_location_id is not None:
                    assert data.opening_qty is not None
                    assert data.opening_unit_cost_zar is not None
                    opening_date = data.opening_date or datetime.date.today()
                    await self.stock_movements.apply_incoming_qty(
                        sku_id=sku.id,
                        location_id=data.opening_location_id,
                        qty=data.opening_qty,
                        unit_cost_zar=data.opening_unit_cost_zar,
                        user_id=user_id,
                        source=UnitCostAuditSource.OPENING,
                        note=f"Opening stock {opening_date.isoformat()}",
                    )
        except IntegrityError as exc:
            await self._raise_integrity_conflict(exc)
        reloaded = await self.crud.get_by_id(sku.id)
        assert reloaded is not None
        return (await self._to_responses([reloaded], user_id))[0]

    async def upload_photo(
        self, sku_id: uuid.UUID, file: UploadFile, user_id: Optional[uuid.UUID] = None
    ) -> SkuResponse:
        from app.services.sku_archive import SkuArchiveService

        await SkuArchiveService(self.db).lock_skus([sku_id])
        sku = await self.crud.get_by_id(sku_id)
        if sku is None:
            raise NotFoundError("SKU not found")
        if sku.is_archived:
            raise ConflictError("Restore the SKU before editing its photo")
        if sku.gallery_photo_keys:
            raise ConflictError("Replace the gallery through the curated catalogue import")

        raw_bytes = await file.read()
        if not raw_bytes:
            raise ValidationError("Photo file is required")

        try:
            image_bytes = await asyncio.to_thread(resize_image, raw_bytes)
        except OSError as exc:
            raise ValidationError(
                "That file isn't a readable image. Use a JPEG, PNG, or WebP."
            ) from exc
        supplemental_keys = (
            sku.setting_photo_storage_key,
            sku.detail_photo_storage_key,
            sku.second_detail_photo_storage_key,
        )
        if any(supplemental_keys):
            digest = hashlib.sha256(image_bytes).hexdigest()
            if any(PurePosixPath(key).stem == digest for key in supplemental_keys if key):
                raise ValidationError("The primary photo must be distinct from the gallery photos")
        relative_path = f"skus/{sku_id}.jpg"
        try:
            storage_key = await asyncio.to_thread(save_bytes, relative_path, image_bytes)
        except FileExistsError as exc:
            raise ConflictError("SKU photo already exists") from exc

        sku.photo_storage_key = storage_key
        await self.crud.commit_refresh(sku)
        reloaded = await self.crud.get_by_id(sku.id)
        assert reloaded is not None
        return (await self._to_responses([reloaded], user_id))[0]

    async def serve_photo(self, sku_id: uuid.UUID, *, slot: int = 1) -> Response:
        sku = await self.crud.get_by_id(sku_id)
        if sku is None:
            raise NotFoundError("SKU photo not found")

        keys = _staff_photo_storage_keys(sku)
        if not 1 <= slot <= len(keys):
            raise NotFoundError("SKU photo not found")
        try:
            data = await asyncio.to_thread(read_bytes, keys[slot - 1])
        except FileNotFoundError as exc:
            raise NotFoundError("SKU photo not found") from exc
        return Response(content=data, media_type="image/jpeg")

    async def _to_responses(
        self, skus: list[Sku], user_id: Optional[uuid.UUID] = None
    ) -> list[SkuResponse]:
        if not skus:
            return []

        hide_cost = True
        if user_id is not None:
            hide_cost = not await PermissionService(self.db).has_permission(
                user_id, STOCK_COST_VIEW
            )

        sku_ids = [sku.id for sku in skus]
        supplier_ids = [
            sku.preferred_supplier_id for sku in skus if sku.preferred_supplier_id is not None
        ]
        landed_costs = await self.unit_cost_audit_crud.latest_landed_costs_by_sku_ids(sku_ids)
        supplier_names = await self.supplier_crud.names_by_ids(supplier_ids)
        kit_ids = await self.bom_crud.parent_ids_with_bom(sku_ids)
        average_costs = await average_costs_by_sku_id(self.db, sku_ids)
        vat_rate = await current_vat_rate(self.db)
        lists = await self._catalogue_lists(skus)

        return [
            self._to_response(
                sku,
                lists=lists,
                vat_rate=vat_rate,
                preferred_supplier_name=(
                    supplier_names.get(sku.preferred_supplier_id)
                    if sku.preferred_supplier_id is not None
                    else None
                ),
                last_landed_cost_zar=None if hide_cost else landed_costs.get(sku.id),
                is_kit=sku.id in kit_ids,
                average_unit_cost_zar=None if hide_cost else average_costs.get(sku.id),
                stockist_below_cost=tier_price_below_cost(
                    sku.stockist_ex_vat, average_costs.get(sku.id)
                ),
                wholesale_below_cost=tier_price_below_cost(
                    sku.wholesale_ex_vat, average_costs.get(sku.id)
                ),
                decorator_below_cost=tier_price_below_cost(
                    sku.decorator_ex_vat, average_costs.get(sku.id)
                ),
                retail_below_cost=tier_price_below_cost(
                    sku.retail_ex_vat, average_costs.get(sku.id)
                ),
            )
            for sku in skus
        ]

    async def _catalogue_lists(self, skus: list[Sku]) -> _CatalogueLists:
        """Names for category, sub-category and materials, in three batched queries."""
        links: dict[uuid.UUID, list[uuid.UUID]] = {}
        for sku_id, material_id in await self.db.execute(
            select(SkuMaterial.sku_id, SkuMaterial.material_id)
            .where(
                SkuMaterial.team_id == tenant_id_ctx.get(),
                SkuMaterial.sku_id.in_([sku.id for sku in skus]),
            )
            .order_by(SkuMaterial.sku_id, SkuMaterial.position)
        ):
            links.setdefault(sku_id, []).append(material_id)
        categories = await categories_by_id(
            self.db, [value for sku in skus for value in (sku.category_id, sku.subcategory_id)]
        )
        materials = await materials_by_id(
            self.db,
            [sku.main_material_id for sku in skus] + [m for ids in links.values() for m in ids],
        )
        return _CatalogueLists(categories, materials, links)

    def _to_response(
        self,
        sku: Sku,
        *,
        lists: _CatalogueLists,
        vat_rate: Decimal,
        preferred_supplier_name: Optional[str] = None,
        last_landed_cost_zar: Optional[Decimal] = None,
        is_kit: bool = False,
        average_unit_cost_zar: Optional[Decimal] = None,
        stockist_below_cost: bool = False,
        wholesale_below_cost: bool = False,
        decorator_below_cost: bool = False,
        retail_below_cost: bool = False,
    ) -> SkuResponse:
        photo_keys = _staff_photo_storage_keys(sku)
        retail_ex = sku.retail_ex_vat
        other_ids = lists.links.get(sku.id, [])
        return SkuResponse(
            is_sellable=sku.is_sellable,
            till_no_stock_required=sku.till_no_stock_required,
            exclude_from_commission=sku.exclude_from_commission,
            storefront_hidden=sku.storefront_hidden,
            is_archived=sku.is_archived,
            archived_at=sku.archived_at,
            archived_by_id=sku.archived_by_id,
            id=sku.id,
            our_ref=sku.our_ref,
            our_barcode=sku.our_barcode,
            name=sku.name,
            design=sku.design,
            fabric=sku.fabric,
            supplier_ref=sku.supplier_ref,
            preferred_supplier_id=sku.preferred_supplier_id,
            preferred_supplier_name=preferred_supplier_name,
            lead_time_days=sku.lead_time_days,
            made_to_order_capacity=sku.made_to_order_capacity,
            made_to_order_lead_time_min_days=sku.made_to_order_lead_time_min_days,
            made_to_order_lead_time_max_days=sku.made_to_order_lead_time_max_days,
            made_to_order_expires_at=sku.made_to_order_expires_at,
            made_to_order_offer_id=sku.made_to_order_offer_id,
            reorder_min=sku.reorder_min,
            last_landed_cost_zar=last_landed_cost_zar,
            category=sku.category,
            category_id=sku.category_id,
            subcategory_id=sku.subcategory_id,
            subcategory=(
                lists.categories[sku.subcategory_id].name
                if sku.subcategory_id in lists.categories
                else None
            ),
            colour_name=sku.colour_name,
            main_material_id=sku.main_material_id,
            main_material=lists.material(sku.main_material_id),
            other_material_ids=other_ids,
            other_materials=[
                summary for summary in map(lists.material, other_ids) if summary is not None
            ],
            sell_multiple=sku.sell_multiple,
            min_sell_qty=sku.min_sell_qty,
            order_up_to=sku.order_up_to,
            do_not_reorder=sku.do_not_reorder,
            swatch_hex=sku.swatch_hex,
            photo_storage_key=(
                sku.gallery_photo_keys[0] if sku.gallery_photo_keys else sku.photo_storage_key
            ),
            gallery_photo_count=(
                len(photo_keys)
                if sku.gallery_photo_keys
                or sku.setting_photo_storage_key
                or sku.detail_photo_storage_key
                or sku.second_detail_photo_storage_key
                else 0
            ),
            **{field: getattr(sku, field) for field in SKU_DETAIL_FIELDS},
            stockist_ex_vat=sku.stockist_ex_vat,
            stockist_inc_vat=inc_vat_or_none(sku.stockist_ex_vat, vat_rate),
            wholesale_ex_vat=sku.wholesale_ex_vat,
            wholesale_inc_vat=inc_vat_or_none(sku.wholesale_ex_vat, vat_rate),
            decorator_ex_vat=sku.decorator_ex_vat,
            decorator_inc_vat=inc_vat_or_none(sku.decorator_ex_vat, vat_rate),
            retail_ex_vat=(
                retail_ex.quantize(CENT, rounding=ROUND_HALF_UP) if retail_ex is not None else None
            ),
            retail_inc_vat=inc_vat_or_none(retail_ex, vat_rate),
            average_unit_cost_zar=average_unit_cost_zar,
            stockist_below_cost=stockist_below_cost,
            wholesale_below_cost=wholesale_below_cost,
            decorator_below_cost=decorator_below_cost,
            retail_below_cost=retail_below_cost,
            carton_count=sku.carton_count,
            is_kit=is_kit,
            created_at=sku.created_at,
            updated_at=sku.updated_at,
        )

    async def _apply_catalogue_fields(
        self,
        sku: Sku,
        data: Union[SkuCreate, SkuUpdate],
        fields_set: set[str],
    ) -> Optional[list[uuid.UUID]]:
        """Validate and write category, materials, finish label, design, selling and reorder
        rules. Everything is checked before anything is written. Returns the other materials
        to store when they change (the caller writes them once the SKU has an id).
        """
        creating = sku.id is None
        errors: list[tuple[str, str]] = []

        # Category: legacy name input resolves to an existing top-level category.
        current_category = sku.category_id
        current_sub = sku.subcategory_id
        target_category = current_category
        if "category" in fields_set:
            name = (data.category or "").strip()
            legacy_id: Optional[uuid.UUID] = None
            if name:
                found = await category_by_name(self.db, name)
                if found is None:
                    errors.append(("category", unknown_category_message(name)))
                else:
                    legacy_id = found.id
            if "category_id" in data.model_fields_set and data.category_id != legacy_id:
                errors.append(("category", "category and category_id name different categories"))
            target_category = legacy_id
        if "category_id" in fields_set and "category" not in fields_set:
            target_category = data.category_id
        target_sub = data.subcategory_id if "subcategory_id" in fields_set else current_sub
        categories = await categories_by_id(self.db, (target_category, target_sub))

        category_row: Optional[SkuCategory] = None
        if target_category is not None:
            category_row = categories.get(target_category)
            field = "category_id" if "category_id" in fields_set else "category"
            if category_row is None:
                errors.append((field, "Category not found"))
            elif category_row.parent_id is not None:
                errors.append(
                    (field, f"'{category_row.name}' is a sub-category; choose a category")
                )
                category_row = None
            elif category_row.is_archived and target_category != current_category:
                errors.append((field, f"Category '{category_row.name}' is archived"))
        if target_sub is not None:
            sub_row = categories.get(target_sub)
            if "subcategory_id" not in fields_set:
                # Changing category clears a sub-category that no longer fits.
                if sub_row is None or sub_row.parent_id != target_category:
                    target_sub = None
            elif target_category is None:
                errors.append(("subcategory_id", "Choose a category before a sub-category"))
            elif sub_row is None:
                errors.append(("subcategory_id", "Sub-category not found"))
            elif sub_row.parent_id != target_category:
                parent = category_row.name if category_row is not None else "this category"
                errors.append(
                    ("subcategory_id", f"'{sub_row.name}' is not a sub-category of {parent}")
                )
            elif sub_row.is_archived and target_sub != current_sub:
                errors.append(("subcategory_id", f"Sub-category '{sub_row.name}' is archived"))

        # Materials: one main, any number of others, never the same one twice.
        current_main = sku.main_material_id
        current_others = [] if creating else await self._other_material_ids(sku.id)
        target_main = data.main_material_id if "main_material_id" in fields_set else current_main
        others_sent = "other_material_ids" in fields_set
        target_others = list(data.other_material_ids or []) if others_sent else list(current_others)
        if len(set(target_others)) != len(target_others):
            errors.append(("other_material_ids", "A material is listed more than once"))
        if target_main is not None and target_main in target_others:
            errors.append(
                (
                    "other_material_ids" if others_sent else "main_material_id",
                    "A material cannot be both the main material and another material",
                )
            )
        materials = await materials_by_id(self.db, (target_main, *target_others))
        if target_main is not None and target_main != current_main:
            main = materials.get(target_main)
            if main is None:
                errors.append(("main_material_id", "Material not found"))
            elif main.is_archived:
                errors.append(("main_material_id", f"Material '{main.name}' is archived"))
        for material_id in dict.fromkeys(target_others):
            if material_id in current_others:
                continue
            other = materials.get(material_id)
            if other is None:
                errors.append(("other_material_ids", "Material not found"))
            elif other.is_archived:
                errors.append(("other_material_ids", f"Material '{other.name}' is archived"))

        # Finish label (skus.fabric): derived from colour name and main material.
        target_colour = data.colour_name if "colour_name" in fields_set else sku.colour_name
        main_material = materials.get(target_main) if target_main is not None else None
        target_fabric = sku.fabric
        # Only a real change rebuilds the label: resending the stored colour or material
        # (null included) must not erase a label that came from the old free-text fabric.
        finish_inputs = {
            field
            for field in ("colour_name", "main_material_id")
            if field in fields_set and getattr(data, field) != getattr(sku, field)
        } | (fields_set & {"fabric"})
        if creating or finish_inputs:
            derived = finish_label(target_colour, main_material.name if main_material else None)
            if derived is not None:
                target_fabric = derived
            elif "fabric" in fields_set and data.fabric and data.fabric.strip():
                target_fabric = data.fabric.strip()
            elif creating or finish_inputs - {"fabric"} or "fabric" in fields_set:
                target_fabric = FABRIC_PLACEHOLDER
        if target_fabric is not None and len(target_fabric) > 255:
            errors.append(("colour_name", "Colour and material together are too long"))
        target_design = data.design if "design" in fields_set else sku.design

        # Selling rules: the minimum is always a multiple of the sell multiple.
        for field in ("sell_multiple", "do_not_reorder"):
            if field in fields_set and getattr(data, field) is None:
                errors.append((field, f"{field} must not be null"))
        multiple = data.sell_multiple if "sell_multiple" in fields_set else sku.sell_multiple
        multiple = multiple or 1
        if "min_sell_qty" in fields_set and data.min_sell_qty is not None:
            minimum = data.min_sell_qty
            if minimum % multiple:
                errors.append(
                    ("min_sell_qty", f"Minimum quantity must be a multiple of {multiple}")
                )
        else:
            # Not sent (or cleared): keep the stored minimum, raised to the next valid
            # multiple when it no longer fits.
            stored = sku.min_sell_qty or 1
            minimum = -(-stored // multiple) * multiple

        reorder_min = data.reorder_min if "reorder_min" in fields_set else sku.reorder_min
        order_up_to = data.order_up_to if "order_up_to" in fields_set else sku.order_up_to
        if reorder_min is not None and order_up_to is not None and order_up_to < reorder_min:
            field = "reorder_min" if "order_up_to" not in fields_set else "order_up_to"
            errors.append(
                (
                    field,
                    f"Order up to ({order_up_to}) must be at least the reorder minimum "
                    f"({reorder_min})",
                )
            )

        if errors:
            raise field_errors(errors)

        if (
            creating
            or target_design != sku.design
            or (target_fabric or "").lower() != (sku.fabric or "").lower()
        ):
            assert target_design is not None and target_fabric is not None
            duplicate = await self.crud.get_by_design_fabric_insensitive(
                target_design, target_fabric, exclude_id=sku.id
            )
            if duplicate is not None:
                raise ConflictError(DUPLICATE_FINISH_MESSAGE)

        # Set or clear category and sub-category together: the database checks the pair.
        sku.category_id = target_category
        sku.subcategory_id = target_sub
        if category_row is not None:
            sku.category = category_row.name
        elif fields_set & {"category", "category_id"} or creating:
            sku.category = None
        sku.colour_name = target_colour
        sku.main_material_id = target_main
        sku.design = target_design
        sku.fabric = target_fabric
        sku.sell_multiple = multiple
        sku.min_sell_qty = minimum
        sku.reorder_min = reorder_min
        sku.order_up_to = order_up_to
        if "do_not_reorder" in fields_set:
            sku.do_not_reorder = data.do_not_reorder
        if target_others != current_others:
            return target_others
        return None

    async def _other_material_ids(self, sku_id: uuid.UUID) -> list[uuid.UUID]:
        return list(
            await self.db.scalars(
                select(SkuMaterial.material_id)
                .where(SkuMaterial.team_id == tenant_id_ctx.get(), SkuMaterial.sku_id == sku_id)
                .order_by(SkuMaterial.position)
            )
        )

    async def _replace_other_materials(
        self, sku_id: uuid.UUID, material_ids: list[uuid.UUID]
    ) -> None:
        # Delete first, as a statement, so re-adding a material never trips the unique key.
        await self.db.execute(
            delete(SkuMaterial).where(
                SkuMaterial.team_id == tenant_id_ctx.get(), SkuMaterial.sku_id == sku_id
            )
        )
        for position, material_id in enumerate(material_ids):
            self.db.add(SkuMaterial(sku_id=sku_id, material_id=material_id, position=position))
        await self.db.flush()

    async def _allocate_csv_barcode(self, our_ref: str) -> str:
        for attempt in range(1, 1000):
            candidate = csv_style_barcode(our_ref, attempt)
            if await self.crud.get_by_our_barcode(candidate) is None:
                return candidate
        raise ConflictError("Could not allocate a unique barcode")

    async def _ensure_unique_fields(self, our_ref: str, our_barcode: str) -> None:
        if await self.crud.get_by_our_ref(our_ref) is not None:
            raise ConflictError("A SKU with this our_ref already exists")
        if await self.crud.get_by_our_barcode(our_barcode) is not None:
            raise ConflictError("A SKU with this our_barcode already exists")

    async def _raise_integrity_conflict(self, exc: IntegrityError) -> None:
        message = str(exc.orig) if exc.orig is not None else str(exc)
        lowered = message.lower()
        if "ix_skus_design_fabric_lower" in lowered or (
            "design" in lowered and "fabric" in lowered
        ):
            raise ConflictError(DUPLICATE_FINISH_MESSAGE) from exc
        if "our_barcode" in lowered:
            raise ConflictError("A SKU with this our_barcode already exists") from exc
        if "our_ref" in lowered:
            raise ConflictError("A SKU with this our_ref already exists") from exc
        raise ConflictError("SKU already exists") from exc


class _CatalogueLists:
    def __init__(
        self,
        categories: dict[uuid.UUID, SkuCategory],
        materials: dict[uuid.UUID, Material],
        links: dict[uuid.UUID, list[uuid.UUID]],
    ) -> None:
        self.categories = categories
        self.materials = materials
        self.links = links

    def material(self, material_id: Optional[uuid.UUID]) -> Optional[SkuMaterialSummary]:
        row = self.materials.get(material_id) if material_id is not None else None
        if row is None:
            return None
        return SkuMaterialSummary(
            id=row.id, name=row.name, family=row.family, is_archived=row.is_archived
        )


def _staff_photo_storage_keys(sku: Sku) -> tuple[str, ...]:
    studio = sku.gallery_photo_keys or [sku.photo_storage_key]
    return tuple(
        key
        for key in (
            *studio,
            sku.setting_photo_storage_key,
            sku.detail_photo_storage_key,
            sku.second_detail_photo_storage_key,
        )
        if key
    )
