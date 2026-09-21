from __future__ import annotations

import asyncio
import datetime
import secrets
import time
import uuid
from decimal import Decimal
from typing import Optional

from fastapi.responses import RedirectResponse, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.customer import CustomerCRUD
from app.crud.lookbook import LookbookCRUD
from app.crud.price_list import PriceListCRUD
from app.crud.quote import QuoteCRUD
from app.crud.sku import SkuCRUD
from app.models.customer import Customer
from app.models.lookbook import (
    Lookbook,
    LookbookEvent,
    LookbookEventType,
    LookbookItem,
    LookbookPriceMode,
    LookbookQuote,
)
from app.models.sku import Sku
from app.models.team import Team
from app.schemas.lookbook import (
    LookbookActivity,
    LookbookActivitySku,
    LookbookCreate,
    LookbookItemStaff,
    LookbookListItem,
    LookbookQuoteLink,
    LookbookResponse,
    PublicLookbookEventsIn,
    PublicLookbookItem,
    PublicLookbookRequestIn,
    PublicLookbookResponse,
)
from app.schemas.page import Page, PageParams
from app.services.object_storage import is_remote_storage_ref, presigned_get_url, read_bytes
from app.services.quotes import QuotesService
from app.services.till_seed import WALK_IN_CUSTOMER_NAME
from app.services.vat import ex_to_inc
from f0rge_core.exceptions import NotFoundError, ValidationError
from f0rge_db.crud import unit_of_work


def _utcnow() -> datetime.datetime:
    return datetime.datetime.utcnow()


_EVENT_HITS: dict[str, list[float]] = {}


def _rate_limit_events(token: str) -> None:
    now = time.monotonic()
    hits = [stamp for stamp in _EVENT_HITS.get(token, []) if now - stamp < 60]
    if len(hits) >= 40:
        raise ValidationError("Too many lookbook events")
    hits.append(now)
    _EVENT_HITS[token] = hits


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

    async def record_events(self, token: str, payload: PublicLookbookEventsIn) -> None:
        _rate_limit_events(token)
        lookbook = await self._live_by_token(token)
        allowed = {item.sku_id for item in lookbook.items}
        rows: list[LookbookEvent] = []
        now = _utcnow()
        for event in payload.events:
            try:
                event_type = LookbookEventType(event.event_type)
            except ValueError as exc:
                raise ValidationError("Unknown lookbook event") from exc
            sku_id = event.sku_id
            if event_type is LookbookEventType.OPEN or event_type is LookbookEventType.SUBMIT:
                sku_id = None
            elif sku_id is None or sku_id not in allowed:
                raise ValidationError("SKU is not on this lookbook")
            if event_type is LookbookEventType.SKU_VISIBLE and event.duration_ms is None:
                raise ValidationError("duration_ms is required for sku_visible")
            rows.append(
                LookbookEvent(
                    lookbook_id=lookbook.id,
                    sku_id=sku_id,
                    event_type=event_type,
                    duration_ms=event.duration_ms,
                    visitor_id=payload.visitor_id,
                    occurred_at=now,
                )
            )
        async with unit_of_work(self.db):
            self.db.add_all(rows)

    async def activity(self, lookbook_id: uuid.UUID) -> LookbookActivity:
        lookbook = await self._get_or_404(lookbook_id)
        events = list(
            (
                await self.db.execute(
                    select(LookbookEvent)
                    .where(LookbookEvent.lookbook_id == lookbook.id)
                    .order_by(LookbookEvent.occurred_at, LookbookEvent.created_at)
                )
            ).scalars()
        )
        opens = sum(1 for event in events if event.event_type is LookbookEventType.OPEN)
        hearts = 0
        submits = sum(1 for event in events if event.event_type is LookbookEventType.SUBMIT)
        by_sku: dict[uuid.UUID, LookbookActivitySku] = {}
        for item in lookbook.items:
            by_sku[item.sku_id] = LookbookActivitySku(
                sku_id=item.sku_id,
                name=item.snapshot_name,
                our_ref=item.snapshot_our_ref,
                dwell_ms=0,
                opens=0,
                hearts=0,
            )
        for event in events:
            if event.sku_id is None or event.sku_id not in by_sku:
                continue
            row = by_sku[event.sku_id]
            if event.event_type is LookbookEventType.SKU_VISIBLE:
                row.dwell_ms += event.duration_ms or 0
            elif event.event_type is LookbookEventType.SKU_OPEN:
                row.opens += 1
            elif event.event_type is LookbookEventType.HEART:
                row.hearts += 1
                hearts += 1
            elif event.event_type is LookbookEventType.UNHEART:
                row.hearts = max(row.hearts - 1, 0)
                hearts = max(hearts - 1, 0)
        quotes = list(
            (
                await self.db.execute(
                    select(LookbookQuote).where(LookbookQuote.lookbook_id == lookbook.id)
                )
            ).scalars()
        )
        quote_links: list[LookbookQuoteLink] = []
        numbered = QuoteCRUD(self.db)
        for link in quotes:
            quote = await numbered.get_by_id(link.quote_id)
            if quote is not None:
                quote_links.append(LookbookQuoteLink(id=quote.id, quote_number=quote.quote_number))
        skus = sorted(by_sku.values(), key=lambda row: row.dwell_ms, reverse=True)
        return LookbookActivity(
            opens=opens,
            hearts=hearts,
            submits=submits,
            skus=skus,
            quotes=quote_links,
        )

    async def request_quote(self, token: str, payload: PublicLookbookRequestIn) -> None:
        lookbook = await self._live_by_token(token)
        by_sku = {item.sku_id: item for item in lookbook.items}
        lines: list[tuple[uuid.UUID, int, Decimal, str]] = []
        for sku_id in list(dict.fromkeys(payload.sku_ids)):
            item = by_sku.get(sku_id)
            if item is None:
                raise ValidationError("SKU is not on this lookbook")
            if item.snapshot_unit_inc_vat is None:
                raise ValidationError("This lookbook has no prices to quote")
            lines.append((item.sku_id, 1, item.snapshot_unit_inc_vat, item.snapshot_name))
        customer_id = lookbook.customer_id
        if customer_id is None:
            walk_in = (
                await self.db.execute(
                    select(Customer).where(Customer.name == WALK_IN_CUSTOMER_NAME).limit(1)
                )
            ).scalar_one_or_none()
            if walk_in is None:
                raise NotFoundError("Walk-in customer not found")
            customer_id = walk_in.id
        notes = f"Lookbook {lookbook.name}: {payload.name} / {payload.contact}"
        quote = await QuotesService(self.db).create_from_snapshots(
            customer_id=customer_id,
            user_id=lookbook.created_by_user_id,
            notes=notes,
            lines=lines,
        )
        async with unit_of_work(self.db):
            self.db.add(LookbookQuote(lookbook_id=lookbook.id, quote_id=quote.id))
            self.db.add(
                LookbookEvent(
                    lookbook_id=lookbook.id,
                    sku_id=None,
                    event_type=LookbookEventType.SUBMIT,
                    duration_ms=None,
                    visitor_id="submit",
                    occurred_at=_utcnow(),
                )
            )

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
