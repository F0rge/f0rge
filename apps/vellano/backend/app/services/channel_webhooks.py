from __future__ import annotations

import base64
import hmac
import hashlib
import json
import logging
import uuid
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.channel import SalesChannelCRUD
from app.models.channel import CHANNEL_SLUG_SHOPIFY
from app.schemas.channel import ChannelOrderCreate, ChannelOrderLineIn
from app.services.channel_orders import ChannelOrderService
from app.services.channel_outbox import ChannelOutboxService, resolve_shopify_credentials
from f0rge_core.exceptions import UnauthorizedError, ValidationError

logger = logging.getLogger(__name__)

_PAID_STATUSES = frozenset({"paid"})
_CANCEL_TOPICS = frozenset({"orders/cancelled", "refunds/create"})
_ORDER_TOPICS = frozenset({"orders/create", "orders/updated", "orders/paid"})


def verify_shopify_hmac(secret: str, body: bytes, header: str) -> bool:
    if not secret or not header:
        return False
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
    computed = base64.b64encode(digest).decode("utf-8")
    return hmac.compare_digest(computed, header)


class ChannelWebhookService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.channels = SalesChannelCRUD(db)
        self.orders = ChannelOrderService(db)
        self.outbox = ChannelOutboxService(db)

    async def handle(self, topic: str, body: bytes, hmac_header: str) -> dict[str, str]:
        channel = await self.channels.get_by_slug(CHANNEL_SLUG_SHOPIFY)
        if channel is None or not channel.enabled:
            raise ValidationError("Shopify channel is disabled")
        _domain, _token, secret = resolve_shopify_credentials(channel)
        if not secret:
            raise ValidationError("Shopify webhook secret is not configured")
        if not verify_shopify_hmac(secret, body, hmac_header):
            raise UnauthorizedError("Invalid Shopify HMAC")
        payload = json.loads(body.decode("utf-8") or "{}")
        actor = await self.orders.actor_user_id()
        topic_norm = (topic or "").strip().lower()
        if topic_norm in _CANCEL_TOPICS:
            return await self._cancel(payload, actor)
        if topic_norm in _ORDER_TOPICS or topic_norm.endswith("/create"):
            return await self._ingest_order(payload, actor)
        return {"status": "ignored"}

    async def _ingest_order(self, payload: dict[str, Any], actor: uuid.UUID) -> dict[str, str]:
        external_id = str(payload.get("id") or "")
        if not external_id:
            raise ValidationError("Shopify order id missing")
        financial = str(payload.get("financial_status") or "").lower()
        paid = financial in _PAID_STATUSES
        lines = []
        for item in payload.get("line_items") or []:
            qty = int(item.get("quantity") or 0)
            if qty < 1:
                continue
            price = item.get("price")
            unit_inc = None
            if price not in (None, ""):
                parsed = Decimal(str(price))
                if parsed > 0:
                    unit_inc = parsed
            variant_id = item.get("variant_id")
            lines.append(
                ChannelOrderLineIn(
                    sku=item.get("sku") or None,
                    qty=qty,
                    unit_inc_vat=unit_inc,
                    variant_id=str(variant_id) if variant_id is not None else None,
                    name=item.get("title") or item.get("name"),
                )
            )
        if not lines:
            raise ValidationError("Shopify order has no sellable lines")
        fulfillment_order_id = _fulfillment_order_id(payload)
        location_gid = _shopify_location_gid(payload)
        data = ChannelOrderCreate(
            channel=CHANNEL_SLUG_SHOPIFY,
            external_id=external_id,
            email=payload.get("email") or payload.get("contact_email"),
            customer_name=_customer_name(payload),
            paid=paid,
            lines=lines,
            shopify_location_gid=location_gid,
            shopify_fulfillment_order_id=fulfillment_order_id,
            payload={
                "lines": [line.model_dump(mode="json") for line in lines],
                "customer_name": _customer_name(payload),
                "shopify_location_gid": location_gid,
                "shopify_fulfillment_order_id": fulfillment_order_id,
                "financial_status": financial,
            },
        )
        # Persist quickly; paid orders process via outbox so Shopify gets 200.
        order = await self.orders.ingest(data, actor, process=False)
        if paid:
            await self.outbox.enqueue_process_order(order.id)
        return {"status": "accepted", "order_id": str(order.id)}

    async def _cancel(self, payload: dict[str, Any], actor: uuid.UUID) -> dict[str, str]:
        # refunds/create uses id=refund_id and order_id=order_id; cancelled orders use id.
        external_id = str(payload.get("order_id") or payload.get("id") or "")
        if not external_id:
            return {"status": "ignored"}
        channel = await self.channels.get_by_slug(CHANNEL_SLUG_SHOPIFY)
        if channel is None:
            return {"status": "ignored"}
        from app.crud.channel import ChannelOrderCRUD

        existing = await ChannelOrderCRUD(self.db).get_by_external(channel.id, external_id)
        if existing is None:
            return {"status": "ignored"}
        await self.orders.cancel(existing.id, actor)
        return {"status": "cancelled", "order_id": str(existing.id)}


def _customer_name(payload: dict[str, Any]) -> Optional[str]:
    customer = payload.get("customer") or {}
    first = customer.get("first_name") or ""
    last = customer.get("last_name") or ""
    name = f"{first} {last}".strip()
    return name or None


def _shopify_location_gid(payload: dict[str, Any]) -> Optional[str]:
    location_id = payload.get("location_id")
    if location_id:
        return f"gid://shopify/Location/{location_id}"
    return None


def _fulfillment_order_id(payload: dict[str, Any]) -> Optional[str]:
    fos = payload.get("fulfillment_orders") or []
    if fos and isinstance(fos, list) and fos[0].get("id"):
        value = fos[0]["id"]
        if str(value).startswith("gid://"):
            return str(value)
        return f"gid://shopify/FulfillmentOrder/{value}"
    return None
