from __future__ import annotations

import asyncio
import datetime
import uuid
from decimal import Decimal
from typing import Optional

from fastapi import UploadFile
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.location import LocationCRUD
from app.crud.sku import SkuCRUD
from app.crud.sku_bom_line import SkuBomLineCRUD
from app.crud.supplier import SupplierCRUD
from app.crud.unit_cost_audit import UnitCostAuditCRUD
from app.models.sku import Sku
from app.models.unit_cost_audit import UnitCostAuditSource
from app.permissions import STOCK_COST_VIEW
from app.services.permissions import PermissionService
from app.schemas.sku import SkuCreate, SkuResponse, SkuUpdate
from app.services.stock_movements import StockMovementService
from app.services.vat import inc_to_ex, inc_vat_or_none, validate_non_negative_price
from app.services.object_storage import (
    is_remote_storage_ref,
    presigned_get_url,
    read_bytes,
    save_bytes,
)
from f0rge_core.exceptions import ConflictError, NotFoundError, ValidationError
from f0rge_db.crud import unit_of_work
from f0rge_storage.images import resize_image


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
        self, category: Optional[str] = None, user_id: Optional[uuid.UUID] = None
    ) -> list[SkuResponse]:
        skus = await self.crud.list_all(category=category)
        return await self._to_responses(skus, user_id)

    async def get(self, sku_id: uuid.UUID, user_id: Optional[uuid.UUID] = None) -> SkuResponse:
        sku = await self.crud.get_by_id(sku_id)
        if sku is None:
            raise NotFoundError("SKU not found")
        return (await self._to_responses([sku], user_id))[0]

    async def update(
        self, sku_id: uuid.UUID, data: SkuUpdate, user_id: Optional[uuid.UUID] = None
    ) -> SkuResponse:
        sku = await self.crud.get_by_id(sku_id)
        if sku is None:
            raise NotFoundError("SKU not found")

        fields_set = data.model_fields_set

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

        if "design" in fields_set or "fabric" in fields_set:
            new_design = data.design if "design" in fields_set else sku.design
            new_fabric = data.fabric if "fabric" in fields_set else sku.fabric
            if (
                await self.crud.get_by_design_fabric_insensitive(
                    new_design,
                    new_fabric,
                    exclude_id=sku.id,
                )
                is not None
            ):
                raise ConflictError("A SKU with this design and fabric already exists")
            if "design" in fields_set:
                assert data.design is not None
                sku.design = data.design
            if "fabric" in fields_set:
                assert data.fabric is not None
                sku.fabric = data.fabric

        if "category" in fields_set:
            sku.category = data.category

        if "preferred_supplier_id" in fields_set:
            if data.preferred_supplier_id is not None:
                supplier = await self.supplier_crud.get_by_id(data.preferred_supplier_id)
                if supplier is None:
                    raise NotFoundError("Supplier not found")
            sku.preferred_supplier_id = data.preferred_supplier_id

        if "lead_time_days" in fields_set:
            sku.lead_time_days = data.lead_time_days

        if "reorder_min" in fields_set:
            sku.reorder_min = data.reorder_min

        if "supplier_ref" in fields_set:
            sku.supplier_ref = data.supplier_ref

        if "carton_count" in fields_set:
            assert data.carton_count is not None
            sku.carton_count = data.carton_count

        if "wholesale_ex_vat" in fields_set and "wholesale_inc_vat" in fields_set:
            raise ValidationError("Cannot set both wholesale_ex_vat and wholesale_inc_vat")
        if "retail_ex_vat" in fields_set and "retail_inc_vat" in fields_set:
            raise ValidationError("Cannot set both retail_ex_vat and retail_inc_vat")

        if "wholesale_ex_vat" in fields_set:
            if data.wholesale_ex_vat is not None:
                validate_non_negative_price(data.wholesale_ex_vat, "wholesale_ex_vat")
            sku.wholesale_ex_vat = data.wholesale_ex_vat
        elif "wholesale_inc_vat" in fields_set:
            if data.wholesale_inc_vat is None:
                sku.wholesale_ex_vat = None
            else:
                validate_non_negative_price(data.wholesale_inc_vat, "wholesale_inc_vat")
                sku.wholesale_ex_vat = inc_to_ex(data.wholesale_inc_vat)

        if "retail_ex_vat" in fields_set:
            if data.retail_ex_vat is not None:
                validate_non_negative_price(data.retail_ex_vat, "retail_ex_vat")
            sku.retail_ex_vat = data.retail_ex_vat
        elif "retail_inc_vat" in fields_set:
            if data.retail_inc_vat is None:
                sku.retail_ex_vat = None
            else:
                validate_non_negative_price(data.retail_inc_vat, "retail_inc_vat")
                sku.retail_ex_vat = inc_to_ex(data.retail_inc_vat)

        try:
            await self.crud.commit_refresh(sku)
        except IntegrityError as exc:
            await self._raise_integrity_conflict(exc)
        reloaded = await self.crud.get_by_id(sku.id)
        assert reloaded is not None
        return (await self._to_responses([reloaded], user_id))[0]

    async def delete(self, sku_id: uuid.UUID) -> None:
        sku = await self.crud.get_by_id(sku_id)
        if sku is None:
            raise NotFoundError("SKU not found")
        try:
            await self.crud.delete_and_commit(sku)
        except IntegrityError as exc:
            raise ConflictError(
                "Cannot delete a SKU that has stock, orders, or sales history."
            ) from exc

    async def create(self, data: SkuCreate, user_id: uuid.UUID) -> SkuResponse:
        await self._ensure_unique_fields(data.design, data.fabric, data.our_ref, data.our_barcode)

        if data.opening_location_id is not None:
            location = await self.location_crud.get_by_id(data.opening_location_id)
            if location is None:
                raise NotFoundError("Location not found")
            if location.is_archived:
                raise ConflictError("Cannot set opening stock at archived location")

        sku = Sku(
            our_ref=data.our_ref,
            our_barcode=data.our_barcode,
            name=data.name,
            design=data.design,
            fabric=data.fabric,
            supplier_ref=data.supplier_ref,
            category=data.category,
            carton_count=data.carton_count,
        )
        try:
            async with unit_of_work(self.db):
                await self.crud.add_and_flush(sku)
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
        sku = await self.crud.get_by_id(sku_id)
        if sku is None:
            raise NotFoundError("SKU not found")

        raw_bytes = await file.read()
        if not raw_bytes:
            raise ValidationError("Photo file is required")

        image_bytes = await asyncio.to_thread(resize_image, raw_bytes)
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

    async def serve_photo(self, sku_id: uuid.UUID) -> Response:
        sku = await self.crud.get_by_id(sku_id)
        if sku is None or not sku.photo_storage_key:
            raise NotFoundError("SKU photo not found")

        storage_key = sku.photo_storage_key
        if is_remote_storage_ref(storage_key):
            url = presigned_get_url(storage_key)
            if url:
                return RedirectResponse(url)

        try:
            data = await asyncio.to_thread(read_bytes, storage_key)
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

        return [
            self._to_response(
                sku,
                preferred_supplier_name=(
                    supplier_names.get(sku.preferred_supplier_id)
                    if sku.preferred_supplier_id is not None
                    else None
                ),
                last_landed_cost_zar=None if hide_cost else landed_costs.get(sku.id),
                is_kit=sku.id in kit_ids,
            )
            for sku in skus
        ]

    def _to_response(
        self,
        sku: Sku,
        *,
        preferred_supplier_name: Optional[str] = None,
        last_landed_cost_zar: Optional[Decimal] = None,
        is_kit: bool = False,
    ) -> SkuResponse:
        return SkuResponse(
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
            reorder_min=sku.reorder_min,
            last_landed_cost_zar=last_landed_cost_zar,
            category=sku.category,
            photo_storage_key=sku.photo_storage_key,
            wholesale_ex_vat=sku.wholesale_ex_vat,
            wholesale_inc_vat=inc_vat_or_none(sku.wholesale_ex_vat),
            retail_ex_vat=sku.retail_ex_vat,
            retail_inc_vat=inc_vat_or_none(sku.retail_ex_vat),
            carton_count=sku.carton_count,
            is_kit=is_kit,
            created_at=sku.created_at,
            updated_at=sku.updated_at,
        )

    async def _ensure_unique_fields(
        self,
        design: str,
        fabric: str,
        our_ref: str,
        our_barcode: str,
    ) -> None:
        if await self.crud.get_by_design_fabric_insensitive(design, fabric) is not None:
            raise ConflictError("A SKU with this design and fabric already exists")
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
            raise ConflictError("A SKU with this design and fabric already exists") from exc
        if "our_barcode" in lowered:
            raise ConflictError("A SKU with this our_barcode already exists") from exc
        if "our_ref" in lowered:
            raise ConflictError("A SKU with this our_ref already exists") from exc
        raise ConflictError("SKU already exists") from exc
