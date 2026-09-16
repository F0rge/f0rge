from __future__ import annotations

import asyncio
import datetime
import secrets
import uuid
from decimal import Decimal
from typing import Optional

from fastapi.responses import RedirectResponse, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.customer import CustomerCRUD
from app.crud.lookbook import LookbookCRUD
from app.crud.price_list import PriceListCRUD
from app.crud.sku import SkuCRUD
from app.models.lookbook import Lookbook, LookbookItem, LookbookPriceMode
from app.models.sku import Sku
from app.models.team import Team
from app.schemas.lookbook import (
    LookbookCreate,
    LookbookItemStaff,
    LookbookListItem,
    LookbookResponse,
    PublicLookbookItem,
    PublicLookbookResponse,
)
from app.schemas.page import Page, PageParams
from app.services.object_storage import is_remote_storage_ref, presigned_get_url, read_bytes
from app.services.vat import ex_to_inc
from f0rge_core.exceptions import NotFoundError, ValidationError
from f0rge_db.crud import unit_of_work


def _utcnow() -> datetime.datetime:
    return datetime.datetime.utcnow()


class LookbooksService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = LookbookCRUD(db)
        self.customer_crud = CustomerCRUD(db)
        self.sku_crud = SkuCRUD(db)
        self.price_list_crud = PriceListCRUD(db)

    async def list(self, params: PageParams) -> Page[LookbookListItem]:
        rows, total = await self.crud.list_page(
            limit=params.limit, offset=params.offset, q=params.q
        )
        return Page(items=[self._to_list_item(row) for row in rows], total=total)

    async def get(self, lookbook_id: uuid.UUID) -> LookbookResponse:
        return self._to_response(await self._get_or_404(lookbook_id))

    async def create(self, data: LookbookCreate, user_id: uuid.UUID) -> LookbookResponse:
        self._validate_price_fields(data)
        customer = None
        if data.customer_id is not None:
            customer = await self.customer_crud.get_by_id(data.customer_id)
            if customer is None:
                raise NotFoundError("Customer not found")
        price_list_id = (
            data.price_list_id if data.price_mode == LookbookPriceMode.PRICE_LIST else None
        )
        if price_list_id is not None:
            await self.price_list_crud.get_by_id(price_list_id)

        sku_ids = list(dict.fromkeys(data.sku_ids))
        items = await self._snapshot_items(sku_ids, data.price_mode, price_list_id)
        lookbook = Lookbook(
            name=data.name.strip(),
            created_by_user_id=user_id,
            customer_id=customer.id if customer is not None else None,
            price_mode=data.price_mode,
            price_list_id=price_list_id,
            token=await self._new_token(),
            expires_at=_utcnow() + datetime.timedelta(days=data.expires_in_days),
            items=items,
        )
        async with unit_of_work(self.db):
            await self.crud.add_and_flush(lookbook)
        return self._to_response(await self._get_or_404(lookbook.id))

    async def revoke(self, lookbook_id: uuid.UUID) -> LookbookResponse:
        lookbook = await self._get_or_404(lookbook_id)
        if lookbook.revoked_at is None:
            lookbook.revoked_at = _utcnow()
            async with unit_of_work(self.db):
                await self.db.flush()
        return self._to_response(await self._get_or_404(lookbook.id))

    async def public_get(self, token: str) -> PublicLookbookResponse:
        lookbook = await self._live_by_token(token)
        company_name = await self.db.scalar(select(Team.name).limit(1))
        return PublicLookbookResponse(
            company_name=company_name or "Company",
            name=lookbook.name,
            price_mode=lookbook.price_mode,
            expires_at=lookbook.expires_at,
            items=[
                PublicLookbookItem(
                    id=item.id,
                    sku_id=item.sku_id,
                    position=item.position,
                    name=item.snapshot_name,
                    our_ref=item.snapshot_our_ref,
                    unit_inc_vat=item.snapshot_unit_inc_vat,
                    photo_path=(
                        f"/api/v1/public/lookbooks/{token}/items/{item.id}/photo"
                        if item.snapshot_photo_key
                        else None
                    ),
                )
                for item in lookbook.items
            ],
        )

    async def serve_public_photo(self, token: str, item_id: uuid.UUID) -> Response:
        lookbook = await self._live_by_token(token)
        item = next((row for row in lookbook.items if row.id == item_id), None)
        if item is None or not item.snapshot_photo_key:
            raise NotFoundError("Lookbook photo not found")
        storage_key = item.snapshot_photo_key
        if is_remote_storage_ref(storage_key):
            url = presigned_get_url(storage_key)
            if url:
                return RedirectResponse(url)
        try:
            data = await asyncio.to_thread(read_bytes, storage_key)
        except FileNotFoundError as exc:
            raise NotFoundError("Lookbook photo not found") from exc
        return Response(content=data, media_type="image/jpeg")

    async def _live_by_token(self, token: str) -> Lookbook:
        lookbook = await self.crud.get_by_token(token)
        if lookbook is None or not self._is_live(lookbook):
            raise NotFoundError("Lookbook not found")
        return lookbook

    async def _get_or_404(self, lookbook_id: uuid.UUID) -> Lookbook:
        lookbook = await self.crud.get_by_id(lookbook_id)
        if lookbook is None:
            raise NotFoundError("Lookbook not found")
        return lookbook

    async def _new_token(self) -> str:
        for _ in range(8):
            token = secrets.token_urlsafe(32)
            if not await self.crud.token_exists(token):
                return token
        raise ValidationError("Could not allocate a lookbook token")

    async def _snapshot_items(
        self,
        sku_ids: list[uuid.UUID],
        price_mode: LookbookPriceMode,
        price_list_id: Optional[uuid.UUID],
    ) -> list[LookbookItem]:
        items: list[LookbookItem] = []
        for position, sku_id in enumerate(sku_ids):
            sku = await self.sku_crud.get_by_id(sku_id)
            if sku is None:
                raise NotFoundError("SKU not found")
            items.append(
                LookbookItem(
                    sku_id=sku.id,
                    position=position,
                    snapshot_name=sku.name,
                    snapshot_our_ref=sku.our_ref,
                    snapshot_unit_inc_vat=await self._snapshot_inc(sku, price_mode, price_list_id),
                    snapshot_photo_key=sku.photo_storage_key,
                )
            )
        return items

    async def _snapshot_inc(
        self,
        sku: Sku,
        price_mode: LookbookPriceMode,
        price_list_id: Optional[uuid.UUID],
    ) -> Optional[Decimal]:
        if price_mode == LookbookPriceMode.HIDDEN:
            return None
        if price_mode == LookbookPriceMode.PRICE_LIST:
            if price_list_id is None:
                raise ValidationError("price_list_id is required when price_mode is price_list")
            unit_ex = await self.price_list_crud.get_item_price(price_list_id, sku.id)
            if unit_ex is None:
                raise ValidationError(f"SKU {sku.our_ref} is not on the price list")
            return ex_to_inc(unit_ex)
        if sku.retail_ex_vat is None or sku.retail_ex_vat <= 0:
            raise ValidationError(f"SKU {sku.our_ref} has no retail price")
        return ex_to_inc(sku.retail_ex_vat)

    @staticmethod
    def _validate_price_fields(data: LookbookCreate) -> None:
        if data.price_mode == LookbookPriceMode.PRICE_LIST:
            if data.price_list_id is None:
                raise ValidationError("price_list_id is required when price_mode is price_list")
            return
        if data.price_list_id is not None:
            raise ValidationError("price_list_id is only valid when price_mode is price_list")

    @staticmethod
    def _is_live(lookbook: Lookbook) -> bool:
        if lookbook.revoked_at is not None:
            return False
        return lookbook.expires_at > _utcnow()

    def _to_list_item(self, lookbook: Lookbook) -> LookbookListItem:
        return LookbookListItem(
            id=lookbook.id,
            name=lookbook.name,
            customer_id=lookbook.customer_id,
            customer_name=lookbook.customer.name if lookbook.customer is not None else None,
            price_mode=lookbook.price_mode,
            sku_count=len(lookbook.items),
            token=lookbook.token,
            expires_at=lookbook.expires_at,
            revoked_at=lookbook.revoked_at,
            created_at=lookbook.created_at,
        )

    def _to_response(self, lookbook: Lookbook) -> LookbookResponse:
        base = self._to_list_item(lookbook)
        return LookbookResponse(
            **base.model_dump(),
            price_list_id=lookbook.price_list_id,
            items=[
                LookbookItemStaff(
                    id=item.id,
                    sku_id=item.sku_id,
                    position=item.position,
                    name=item.snapshot_name,
                    our_ref=item.snapshot_our_ref,
                    unit_inc_vat=item.snapshot_unit_inc_vat,
                )
                for item in lookbook.items
            ],
        )
