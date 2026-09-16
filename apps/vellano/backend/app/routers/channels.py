from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Header, Query, Request, status

from app.dependencies.auth import (
    get_channel_config_service,
    get_channel_ingest_actor,
    get_channel_order_service,
    get_channel_outbox_service,
    get_current_user_id,
    require_channels_manage,
    require_deliveries_mutate,
)
from app.models.channel import ChannelOrderStatus
from app.schemas.channel import (
    ChannelApiKeyCreate,
    ChannelApiKeyCreated,
    ChannelApiKeyResponse,
    ChannelConfigResponse,
    ChannelListingCreate,
    ChannelListingResponse,
    ChannelOrderCreate,
    ChannelOrderResponse,
    ChannelOutboxResponse,
    ChannelResponse,
    ChannelSettingsUpdate,
    ShopifyConnectUpdate,
)
from app.schemas.page import Page, PageParams, get_page_params
from app.services.channel_api_keys import ChannelApiKeyService
from app.services.channel_atp import ChannelAtpService
from app.services.channel_config import ChannelConfigService
from app.services.channel_orders import ChannelOrderService
from app.services.channel_outbox import ChannelOutboxService
from app.services.channel_webhooks import ChannelWebhookService
from app.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession

channels_router = APIRouter(prefix="/api/v1/channels", tags=["channels"])


@channels_router.get("", response_model=ChannelConfigResponse)
async def get_channel_config(
    _: uuid.UUID = Depends(get_current_user_id),
    service: ChannelConfigService = Depends(get_channel_config_service),
) -> ChannelConfigResponse:
    return await service.get_config()


@channels_router.patch("/settings", response_model=ChannelConfigResponse)
async def update_channel_settings(
    body: ChannelSettingsUpdate,
    _: uuid.UUID = Depends(require_channels_manage),
    service: ChannelConfigService = Depends(get_channel_config_service),
) -> ChannelConfigResponse:
    atp = ChannelAtpService(service.db)
    await atp.update_settings(
        atp_mode=body.atp_mode,
        atp_location_id=body.atp_location_id,
        maps=body.maps,
        atp_location_id_set="atp_location_id" in body.model_fields_set,
    )
    return await service.get_config()


@channels_router.patch("/shopify", response_model=ChannelResponse)
async def connect_shopify(
    body: ShopifyConnectUpdate,
    _: uuid.UUID = Depends(require_channels_manage),
    service: ChannelConfigService = Depends(get_channel_config_service),
) -> ChannelResponse:
    return await service.connect_shopify(body)


@channels_router.get("/shopify/locations")
async def list_shopify_locations(
    _: uuid.UUID = Depends(require_channels_manage),
    service: ChannelConfigService = Depends(get_channel_config_service),
):
    return await service.shopify_locations()


@channels_router.get("/listings", response_model=list[ChannelListingResponse])
async def list_listings(
    _: uuid.UUID = Depends(get_current_user_id),
    service: ChannelConfigService = Depends(get_channel_config_service),
) -> list[ChannelListingResponse]:
    return await service.list_listings()


@channels_router.post(
    "/listings",
    response_model=ChannelListingResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upsert_listing(
    body: ChannelListingCreate,
    _: uuid.UUID = Depends(require_channels_manage),
    service: ChannelConfigService = Depends(get_channel_config_service),
) -> ChannelListingResponse:
    return await service.upsert_listing(body)


@channels_router.get("/atp")
async def list_atp(
    sku: Optional[str] = Query(default=None),
    _: uuid.UUID = Depends(get_channel_ingest_actor),
    service: ChannelConfigService = Depends(get_channel_config_service),
):
    return await ChannelAtpService(service.db).list_atp(our_ref=sku)


@channels_router.get("/api-keys", response_model=list[ChannelApiKeyResponse])
async def list_api_keys(
    user_id: uuid.UUID = Depends(require_channels_manage),
    db: AsyncSession = Depends(get_db),
) -> list[ChannelApiKeyResponse]:
    del user_id
    return await ChannelApiKeyService(db).list()


@channels_router.post(
    "/api-keys",
    response_model=ChannelApiKeyCreated,
    status_code=status.HTTP_201_CREATED,
)
async def create_api_key(
    body: ChannelApiKeyCreate,
    user_id: uuid.UUID = Depends(require_channels_manage),
    db: AsyncSession = Depends(get_db),
) -> ChannelApiKeyCreated:
    return await ChannelApiKeyService(db).create(body.name, user_id)


@channels_router.delete("/api-keys/{key_id}", response_model=ChannelApiKeyResponse)
async def revoke_api_key(
    key_id: uuid.UUID,
    _: uuid.UUID = Depends(require_channels_manage),
    db: AsyncSession = Depends(get_db),
) -> ChannelApiKeyResponse:
    return await ChannelApiKeyService(db).revoke(key_id)


@channels_router.get("/orders", response_model=Page[ChannelOrderResponse])
async def list_channel_orders(
    params: PageParams = Depends(get_page_params),
    status_filter: Optional[ChannelOrderStatus] = Query(default=None, alias="status"),
    channel: Optional[str] = None,
    _: uuid.UUID = Depends(get_current_user_id),
    service: ChannelOrderService = Depends(get_channel_order_service),
) -> Page[ChannelOrderResponse]:
    items, total = await service.list_page(
        limit=params.limit,
        offset=params.offset,
        q=params.q,
        status=status_filter,
        channel=channel,
    )
    return Page(items=items, total=total)


@channels_router.post(
    "/orders",
    response_model=ChannelOrderResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_channel_order(
    body: ChannelOrderCreate,
    user_id: Optional[uuid.UUID] = Depends(get_channel_ingest_actor),
    service: ChannelOrderService = Depends(get_channel_order_service),
) -> ChannelOrderResponse:
    return await service.ingest(body, user_id, process=body.paid)


@channels_router.get("/orders/{order_id}", response_model=ChannelOrderResponse)
async def get_channel_order(
    order_id: uuid.UUID,
    _: uuid.UUID = Depends(get_current_user_id),
    service: ChannelOrderService = Depends(get_channel_order_service),
) -> ChannelOrderResponse:
    return await service.get(order_id)


@channels_router.post("/orders/{order_id}/process", response_model=ChannelOrderResponse)
async def process_channel_order(
    order_id: uuid.UUID,
    user_id: Optional[uuid.UUID] = Depends(get_channel_ingest_actor),
    service: ChannelOrderService = Depends(get_channel_order_service),
) -> ChannelOrderResponse:
    return await service.process(order_id, user_id)


@channels_router.post("/orders/{order_id}/fulfill", response_model=ChannelOrderResponse)
async def fulfill_channel_order(
    order_id: uuid.UUID,
    user_id: uuid.UUID = Depends(require_deliveries_mutate),
    service: ChannelOrderService = Depends(get_channel_order_service),
) -> ChannelOrderResponse:
    return await service.fulfill(order_id, user_id)


@channels_router.post("/orders/{order_id}/cancel", response_model=ChannelOrderResponse)
async def cancel_channel_order(
    order_id: uuid.UUID,
    user_id: uuid.UUID = Depends(require_channels_manage),
    service: ChannelOrderService = Depends(get_channel_order_service),
) -> ChannelOrderResponse:
    return await service.cancel(order_id, user_id)


@channels_router.get("/outbox", response_model=list[ChannelOutboxResponse])
async def list_outbox(
    _: uuid.UUID = Depends(require_channels_manage),
    service: ChannelOutboxService = Depends(get_channel_outbox_service),
) -> list[ChannelOutboxResponse]:
    return await service.list_recent()


@channels_router.post("/outbox/drain")
async def drain_outbox(
    _: uuid.UUID = Depends(require_channels_manage),
    service: ChannelOutboxService = Depends(get_channel_outbox_service),
) -> dict[str, int]:
    processed = await service.drain()
    return {"processed": processed}


@channels_router.post("/shopify/webhooks")
async def shopify_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_shopify_hmac_sha256: str = Header(default=""),
    x_shopify_topic: str = Header(default=""),
):
    body = await request.body()
    return await ChannelWebhookService(db).handle(x_shopify_topic, body, x_shopify_hmac_sha256)
