from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.channel import ChannelAtpMode, ChannelOrderStatus, ChannelOutboxStatus


class ChannelLocationMapUpdate(BaseModel):
    location_id: uuid.UUID
    shopify_location_gid: Optional[str] = None
    include_in_atp: bool = True


class ChannelLocationMapResponse(BaseModel):
    id: uuid.UUID
    location_id: uuid.UUID
    location_name: str
    location_type: str
    shopify_location_gid: Optional[str] = None
    include_in_atp: bool

    model_config = ConfigDict(from_attributes=True)


class ChannelSettingsUpdate(BaseModel):
    atp_mode: Optional[ChannelAtpMode] = None
    atp_location_id: Optional[uuid.UUID] = None
    maps: Optional[list[ChannelLocationMapUpdate]] = None


class ShopifyConnectUpdate(BaseModel):
    shop_domain: Optional[str] = None
    admin_token: Optional[str] = None
    webhook_secret: Optional[str] = None
    enabled: Optional[bool] = None


class ChannelResponse(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    enabled: bool
    shopify_shop_domain: Optional[str] = None
    has_shopify_token: bool = False
    has_webhook_secret: bool = False

    model_config = ConfigDict(from_attributes=True)


class ChannelConfigResponse(BaseModel):
    atp_mode: ChannelAtpMode
    atp_location_id: Optional[uuid.UUID] = None
    channels: list[ChannelResponse]
    maps: list[ChannelLocationMapResponse]
    listing_count: int
    sku_count: int
    outbox_failed: int


class ChannelListingCreate(BaseModel):
    sku_id: uuid.UUID
    channel: str = "shopify"
    external_variant_id: Optional[str] = None
    external_inventory_item_id: Optional[str] = None
    external_sku: Optional[str] = None


class ChannelListingResponse(BaseModel):
    id: uuid.UUID
    channel: str
    sku_id: uuid.UUID
    our_ref: str
    sku_name: str
    external_variant_id: Optional[str] = None
    external_inventory_item_id: Optional[str] = None
    external_sku: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ChannelApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)


class ChannelApiKeyCreated(BaseModel):
    id: uuid.UUID
    name: str
    key_prefix: str
    token: str
    created_at: datetime.datetime


class ChannelApiKeyResponse(BaseModel):
    id: uuid.UUID
    name: str
    key_prefix: str
    created_at: datetime.datetime
    last_used_at: Optional[datetime.datetime] = None
    revoked_at: Optional[datetime.datetime] = None


class ChannelOrderLineIn(BaseModel):
    sku: Optional[str] = None
    sku_id: Optional[uuid.UUID] = None
    qty: int = Field(gt=0)
    unit_inc_vat: Optional[Decimal] = None
    variant_id: Optional[str] = None
    inventory_item_id: Optional[str] = None
    name: Optional[str] = None


class ChannelOrderCreate(BaseModel):
    channel: str = "manual"
    external_id: str = Field(min_length=1, max_length=64)
    email: Optional[str] = None
    customer_name: Optional[str] = None
    paid: bool = True
    lines: list[ChannelOrderLineIn] = Field(min_length=1)
    shopify_location_gid: Optional[str] = None
    shopify_fulfillment_order_id: Optional[str] = None
    payload: Optional[dict] = None


class ChannelOrderLineOut(BaseModel):
    sku_id: Optional[uuid.UUID] = None
    our_ref: Optional[str] = None
    qty: int
    location_id: Optional[uuid.UUID] = None


class ChannelOrderResponse(BaseModel):
    id: uuid.UUID
    channel: str
    external_order_id: str
    status: ChannelOrderStatus
    email: Optional[str] = None
    customer_id: Optional[uuid.UUID] = None
    invoice_id: Optional[uuid.UUID] = None
    invoice_number: Optional[str] = None
    pick_id: Optional[uuid.UUID] = None
    delivery_id: Optional[uuid.UUID] = None
    error_message: Optional[str] = None
    allocations: list[dict]
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class AtpRow(BaseModel):
    sku_id: uuid.UUID
    our_ref: str
    available: int
    locations: list[dict]


class ChannelOutboxResponse(BaseModel):
    id: uuid.UUID
    kind: str
    status: ChannelOutboxStatus
    attempts: int
    last_error: Optional[str] = None
    sku_id: Optional[uuid.UUID] = None
    channel_order_id: Optional[uuid.UUID] = None
    available_at: datetime.datetime
    created_at: datetime.datetime


class ShopifyLocationResponse(BaseModel):
    gid: str
    name: str
