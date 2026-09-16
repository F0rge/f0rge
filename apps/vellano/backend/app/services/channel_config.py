from __future__ import annotations


from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.channel import ChannelListingCRUD, ChannelOutboxCRUD, SalesChannelCRUD
from app.crud.sku import SkuCRUD
from app.models.channel import CHANNEL_SLUG_SHOPIFY, ChannelListing, SalesChannel
from app.models.sku import Sku
from app.schemas.channel import (
    ChannelConfigResponse,
    ChannelListingCreate,
    ChannelListingResponse,
    ChannelResponse,
    ShopifyConnectUpdate,
)
from app.services.channel_atp import ChannelAtpService
from app.services.channel_outbox import resolve_shopify_credentials
from app.services.shopify_admin import ShopifyAdminClient
from f0rge_core.exceptions import ConflictError, NotFoundError
from f0rge_db.crud import unit_of_work


class ChannelConfigService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.channels = SalesChannelCRUD(db)
        self.listings = ChannelListingCRUD(db)
        self.skus = SkuCRUD(db)
        self.atp = ChannelAtpService(db)
        self.outbox = ChannelOutboxCRUD(db)

    async def get_config(self) -> ChannelConfigResponse:
        mode, location_id = await self.atp.mode_and_location()
        channels = [self._channel_response(row) for row in await self.channels.list_all()]
        shopify = await self.channels.get_by_slug(CHANNEL_SLUG_SHOPIFY)
        listing_count = 0
        if shopify is not None:
            listing_count = await self.listings.count_for_channel(shopify.id)
        sku_count = int((await self.db.execute(select(func.count()).select_from(Sku))).scalar_one())
        return ChannelConfigResponse(
            atp_mode=mode,
            atp_location_id=location_id,
            channels=channels,
            maps=await self.atp.map_responses(),
            listing_count=listing_count,
            sku_count=sku_count,
            outbox_failed=await self.outbox.count_failed(),
        )

    async def connect_shopify(self, data: ShopifyConnectUpdate) -> ChannelResponse:
        channel = await self.channels.get_by_slug(CHANNEL_SLUG_SHOPIFY)
        if channel is None:
            raise NotFoundError("Shopify channel not seeded")
        async with unit_of_work(self.db):
            if data.shop_domain is not None:
                channel.shopify_shop_domain = data.shop_domain.strip() or None
            if data.admin_token:
                channel.shopify_admin_token = data.admin_token.strip()
            if data.webhook_secret:
                channel.shopify_webhook_secret = data.webhook_secret.strip()
            if data.enabled is not None:
                channel.enabled = data.enabled
        reloaded = await self.channels.get_by_slug(CHANNEL_SLUG_SHOPIFY)
        assert reloaded is not None
        return self._channel_response(reloaded)

    async def upsert_listing(self, data: ChannelListingCreate) -> ChannelListingResponse:
        channel = await self.channels.get_by_slug(data.channel)
        if channel is None:
            raise NotFoundError("Channel not found")
        sku = await self.skus.get_by_id(data.sku_id)
        if sku is None:
            raise NotFoundError("SKU not found")
        existing = await self.listings.get_by_sku(channel.id, sku.id)
        async with unit_of_work(self.db):
            if existing is None:
                existing = ChannelListing(
                    channel_id=channel.id,
                    sku_id=sku.id,
                    external_variant_id=data.external_variant_id,
                    external_inventory_item_id=data.external_inventory_item_id,
                    external_sku=data.external_sku or sku.our_ref,
                )
                await self.listings.add_and_flush(existing)
            else:
                if data.external_variant_id is not None:
                    existing.external_variant_id = data.external_variant_id
                if data.external_inventory_item_id is not None:
                    existing.external_inventory_item_id = data.external_inventory_item_id
                if data.external_sku is not None:
                    existing.external_sku = data.external_sku
        existing = await self.listings.get_by_sku(channel.id, sku.id)
        assert existing is not None
        existing.sku = sku
        return self._listing_response(existing, channel.slug)

    async def list_listings(
        self, channel: str = CHANNEL_SLUG_SHOPIFY
    ) -> list[ChannelListingResponse]:
        row = await self.channels.get_by_slug(channel)
        if row is None:
            raise NotFoundError("Channel not found")
        return [
            self._listing_response(item, row.slug)
            for item in await self.listings.list_for_channel(row.id)
        ]

    async def shopify_locations(self) -> list[dict]:
        channel = await self.channels.get_by_slug(CHANNEL_SLUG_SHOPIFY)
        if channel is None:
            raise NotFoundError("Shopify channel not seeded")
        domain, token, _secret = resolve_shopify_credentials(channel)
        if not domain or not token:
            raise ConflictError("Shopify is not connected")
        client = ShopifyAdminClient(domain, token)
        return await client.list_locations()

    def _channel_response(self, row: SalesChannel) -> ChannelResponse:
        domain, token, secret = resolve_shopify_credentials(row)
        return ChannelResponse(
            id=row.id,
            slug=row.slug,
            name=row.name,
            enabled=row.enabled,
            shopify_shop_domain=domain or row.shopify_shop_domain,
            has_shopify_token=bool(token),
            has_webhook_secret=bool(secret),
        )

    @staticmethod
    def _listing_response(row: ChannelListing, slug: str) -> ChannelListingResponse:
        return ChannelListingResponse(
            id=row.id,
            channel=slug,
            sku_id=row.sku_id,
            our_ref=row.sku.our_ref,
            sku_name=row.sku.name,
            external_variant_id=row.external_variant_id,
            external_inventory_item_id=row.external_inventory_item_id,
            external_sku=row.external_sku,
        )
