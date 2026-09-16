from __future__ import annotations

import datetime
import logging
import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.crud.channel import (
    ChannelListingCRUD,
    ChannelLocationMapCRUD,
    ChannelOrderCRUD,
    ChannelOutboxCRUD,
    SalesChannelCRUD,
)
from app.models.channel import (
    CHANNEL_SLUG_SHOPIFY,
    ChannelAtpMode,
    ChannelOrderStatus,
    ChannelOutbox,
    ChannelOutboxKind,
    ChannelOutboxStatus,
)
from app.schemas.channel import ChannelOutboxResponse
from app.services.channel_atp import ChannelAtpService
from app.services.shopify_admin import ShopifyAdminClient
from f0rge_core.exceptions import ConflictError
from f0rge_db.crud import unit_of_work

_PROCESSING_LEASE = datetime.timedelta(minutes=5)

logger = logging.getLogger(__name__)


def resolve_shopify_credentials(channel) -> tuple[str, str, str]:
    domain = (settings.shopify_shop_domain or channel.shopify_shop_domain or "").strip()
    token = (settings.shopify_admin_token or channel.shopify_admin_token or "").strip()
    secret = (settings.shopify_webhook_secret or channel.shopify_webhook_secret or "").strip()
    return domain, token, secret


class ChannelOutboxService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = ChannelOutboxCRUD(db)
        self.channels = SalesChannelCRUD(db)
        self.listings = ChannelListingCRUD(db)
        self.maps = ChannelLocationMapCRUD(db)
        self.orders = ChannelOrderCRUD(db)
        self.atp = ChannelAtpService(db)

    async def enqueue_inventory_push(self, sku_id: uuid.UUID) -> None:
        shopify = await self.channels.get_by_slug(CHANNEL_SLUG_SHOPIFY)
        if shopify is None or not shopify.enabled:
            return
        existing = await self.crud.get_pending_inventory(sku_id)
        if existing is not None:
            return
        self.db.add(
            ChannelOutbox(
                kind=ChannelOutboxKind.INVENTORY_PUSH,
                status=ChannelOutboxStatus.PENDING,
                payload={},
                sku_id=sku_id,
                available_at=datetime.datetime.utcnow(),
            )
        )
        await self.db.flush()

    async def enqueue_listed_inventory(self) -> None:
        shopify = await self.channels.get_by_slug(CHANNEL_SLUG_SHOPIFY)
        if shopify is None or not shopify.enabled:
            return
        listings = await self.listings.list_for_channel(shopify.id)
        async with unit_of_work(self.db):
            for listing in listings:
                await self.enqueue_inventory_push(listing.sku_id)

    async def enqueue_fulfillment(self, channel_order_id: uuid.UUID) -> None:
        self.db.add(
            ChannelOutbox(
                kind=ChannelOutboxKind.FULFILLMENT_PUSH,
                status=ChannelOutboxStatus.PENDING,
                payload={},
                channel_order_id=channel_order_id,
                available_at=datetime.datetime.utcnow(),
            )
        )
        await self.db.flush()

    async def enqueue_process_order(self, channel_order_id: uuid.UUID) -> None:
        existing = await self.crud.get_open_process_order(channel_order_id)
        if existing is not None:
            return
        async with unit_of_work(self.db):
            self.db.add(
                ChannelOutbox(
                    kind=ChannelOutboxKind.PROCESS_ORDER,
                    status=ChannelOutboxStatus.PENDING,
                    payload={},
                    channel_order_id=channel_order_id,
                    available_at=datetime.datetime.utcnow(),
                )
            )
            await self.db.flush()

    async def list_recent(self) -> list[ChannelOutboxResponse]:
        return [
            ChannelOutboxResponse(
                id=row.id,
                kind=row.kind.value,
                status=row.status,
                attempts=row.attempts,
                last_error=row.last_error,
                sku_id=row.sku_id,
                channel_order_id=row.channel_order_id,
                available_at=row.available_at,
                created_at=row.created_at,
            )
            for row in await self.crud.list_recent()
        ]

    async def drain(self, limit: int = 25) -> int:
        processed = 0
        now = datetime.datetime.utcnow()
        stmt = (
            select(ChannelOutbox)
            .where(
                ChannelOutbox.available_at <= now,
                ChannelOutbox.status.in_(
                    (ChannelOutboxStatus.PENDING, ChannelOutboxStatus.PROCESSING)
                ),
            )
            .order_by(ChannelOutbox.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        async with unit_of_work(self.db):
            rows = list((await self.db.execute(stmt)).scalars().all())
            lease_until = datetime.datetime.utcnow() + _PROCESSING_LEASE
            for row in rows:
                row.status = ChannelOutboxStatus.PROCESSING
                row.available_at = lease_until
            await self.db.flush()
        for row in rows:
            try:
                await self._handle(row)
                async with unit_of_work(self.db):
                    current = await self.db.get(ChannelOutbox, row.id)
                    if current is not None:
                        current.status = ChannelOutboxStatus.DONE
                        current.last_error = None
                processed += 1
            except Exception as exc:
                logger.exception("channel outbox %s failed", row.id)
                async with unit_of_work(self.db):
                    current = await self.db.get(ChannelOutbox, row.id)
                    if current is not None:
                        current.attempts += 1
                        current.last_error = str(exc)[:2000]
                        if current.attempts >= 8:
                            current.status = ChannelOutboxStatus.FAILED
                        else:
                            current.status = ChannelOutboxStatus.PENDING
                            current.available_at = datetime.datetime.utcnow() + datetime.timedelta(
                                seconds=min(300, 5 * current.attempts)
                            )
        return processed

    async def _handle(self, row: ChannelOutbox) -> None:
        if row.kind == ChannelOutboxKind.INVENTORY_PUSH and row.sku_id is not None:
            await self._push_inventory(row.sku_id)
            return
        if row.kind == ChannelOutboxKind.PROCESS_ORDER and row.channel_order_id is not None:
            from app.services.channel_orders import ChannelOrderService

            service = ChannelOrderService(self.db)
            actor = await service.actor_user_id()
            result = await service.process(row.channel_order_id, actor)
            if result.status not in (
                ChannelOrderStatus.POSTED,
                ChannelOrderStatus.CANCELLED,
                ChannelOrderStatus.REFUNDED,
            ):
                raise ConflictError(
                    result.error_message or f"Channel order not posted ({result.status.value})"
                )
            return
        if row.kind == ChannelOutboxKind.FULFILLMENT_PUSH and row.channel_order_id is not None:
            await self._push_fulfillment(row.channel_order_id)

    async def _shopify_client(self) -> Optional[ShopifyAdminClient]:
        channel = await self.channels.get_by_slug(CHANNEL_SLUG_SHOPIFY)
        if channel is None or not channel.enabled:
            return None
        domain, token, _secret = resolve_shopify_credentials(channel)
        if not domain or not token:
            return None
        return ShopifyAdminClient(domain, token)

    async def _push_inventory(self, sku_id: uuid.UUID) -> None:
        client = await self._shopify_client()
        if client is None:
            return
        channel = await self.channels.get_by_slug(CHANNEL_SLUG_SHOPIFY)
        assert channel is not None
        listing = await self.listings.get_by_sku(channel.id, sku_id)
        if listing is None or not listing.external_inventory_item_id:
            return
        maps = [
            row for row in await self.maps.list_for_channel(channel.id) if row.shopify_location_gid
        ]
        if not maps:
            return
        mode, atp_location_id = await self.atp.mode_and_location()
        quantities: list[dict] = []
        if mode == ChannelAtpMode.MAPPED:
            for row in maps:
                qty = await self.atp._on_hand(sku_id, row.location_id)
                if await self.atp._location_locked(row.location_id):
                    qty = 0
                quantities.append(
                    {
                        "inventoryItemId": listing.external_inventory_item_id,
                        "locationId": row.shopify_location_gid,
                        "quantity": qty,
                    }
                )
        else:
            qty = await self.atp.available_for_sku(sku_id)
            target = None
            if atp_location_id is not None:
                for row in maps:
                    if row.location_id == atp_location_id:
                        target = row
                        break
            if target is None:
                target = maps[0]
            quantities.append(
                {
                    "inventoryItemId": listing.external_inventory_item_id,
                    "locationId": target.shopify_location_gid,
                    "quantity": qty,
                }
            )
        await client.set_available_quantities(
            quantities,
            reference=f"gid://vellano/Sku/{sku_id}",
        )

    async def _push_fulfillment(self, channel_order_id: uuid.UUID) -> None:
        client = await self._shopify_client()
        if client is None:
            return
        order = await self.orders.get_by_id(channel_order_id)
        if order is None:
            return
        fo_id = order.shopify_fulfillment_order_id
        if not fo_id:
            fo_id = await client.fulfillment_order_id_for_order(order.external_order_id)
            if fo_id:
                async with unit_of_work(self.db):
                    order.shopify_fulfillment_order_id = fo_id
        if not fo_id:
            return
        await client.create_fulfillment(fo_id)
