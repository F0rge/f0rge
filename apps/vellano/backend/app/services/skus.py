from __future__ import annotations

import asyncio
import uuid

from fastapi import UploadFile
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.sku import SkuCRUD
from app.models.sku import Sku
from app.schemas.sku import SkuCreate, SkuResponse
from app.services.object_storage import (
    is_remote_storage_ref,
    presigned_get_url,
    read_bytes,
    save_bytes,
)
from f0rge_core.exceptions import ConflictError, NotFoundError, ValidationError
from f0rge_storage.images import resize_image


class SkuService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = SkuCRUD(db)

    async def list(self) -> list[SkuResponse]:
        skus = await self.crud.list_all()
        return [SkuResponse.model_validate(s) for s in skus]

    async def get(self, sku_id: uuid.UUID) -> SkuResponse:
        sku = await self.crud.get_by_id(sku_id)
        if sku is None:
            raise NotFoundError("SKU not found")
        return SkuResponse.model_validate(sku)

    async def create(self, data: SkuCreate) -> SkuResponse:
        await self._ensure_unique_fields(data.design, data.fabric, data.our_ref, data.our_barcode)

        sku = Sku(
            our_ref=data.our_ref,
            our_barcode=data.our_barcode,
            name=data.name,
            design=data.design,
            fabric=data.fabric,
            supplier_ref=data.supplier_ref,
        )
        await self.crud.add_and_flush(sku)
        try:
            await self.crud.commit_refresh(sku)
        except IntegrityError as exc:
            await self._raise_integrity_conflict(exc)
        reloaded = await self.crud.get_by_id(sku.id)
        assert reloaded is not None
        return SkuResponse.model_validate(reloaded)

    async def upload_photo(self, sku_id: uuid.UUID, file: UploadFile) -> SkuResponse:
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
        return SkuResponse.model_validate(reloaded)

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
