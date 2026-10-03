from __future__ import annotations

import datetime
import uuid
from typing import Literal, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.ops_commerce_orders import OpsCommerceOrdersCRUD
from app.models.delivery import DeliveryStatus
from app.models.ops_commerce_fulfillment_event import OpsCommerceFulfillmentEvent
from app.models.ops_commerce_order import OpsCommerceOrder
from app.schemas.ops_commerce_order import FulfillmentStatus, FulfillmentType
from f0rge_core.exceptions import ConflictError, NotFoundError
from f0rge_db.crud import unit_of_work

CollectionStatus = Literal["ready_for_collection", "collected"]


class StorefrontFulfillmentService:
    """Translate Firstout's staff actions into a durable customer status stream."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.orders = OpsCommerceOrdersCRUD(db)

    async def update_collection_status(
        self,
        handoff_id: uuid.UUID,
        status: CollectionStatus,
    ) -> OpsCommerceOrder:
        async with unit_of_work(self.db):
            handoff = await self.orders.get_by_id(handoff_id, for_update=True)
            if handoff is None:
                raise NotFoundError("Storefront order not found")
            if self._fulfillment_type(handoff) != "collection":
                raise ConflictError("This Storefront order is not for collection")
            if handoff.status != "imported":
                raise ConflictError(
                    "The paid order must be imported before collection can progress"
                )
            await self._transition(handoff, status, expected_type="collection")
        return await self.orders.get_by_id(handoff_id)  # type: ignore[return-value]

    async def mark_cancelled(self, handoff: OpsCommerceOrder) -> None:
        """Append the cancellation to the same durable customer status stream."""
        if handoff.status != "imported":
            raise ConflictError("The paid order must be imported before cancellation")
        if handoff.fulfillment_status != "confirmed":
            raise ConflictError("Only an unfulfilled Storefront order can be cancelled")
        fulfillment_type = self._fulfillment_type(handoff)
        if fulfillment_type is None:
            raise ConflictError("Storefront order fulfilment type is invalid")
        await self._transition(
            handoff,
            "cancelled",
            expected_type=fulfillment_type,
        )

    async def record_delivery_transition(
        self,
        sales_order_id: uuid.UUID,
        delivery_status: DeliveryStatus,
    ) -> None:
        status_for_delivery = {
            DeliveryStatus.PACKED: "ready_for_delivery",
            DeliveryStatus.LOADED: "out_for_delivery",
            DeliveryStatus.DELIVERED: "delivered",
        }
        next_status = status_for_delivery.get(delivery_status)
        if next_status is None:
            return
        handoff = await self.db.scalar(
            select(OpsCommerceOrder)
            .where(OpsCommerceOrder.sales_order_id == sales_order_id)
            .with_for_update()
        )
        if handoff is None or self._fulfillment_type(handoff) != "delivery":
            return
        if handoff.status != "imported":
            return
        current_rank = self._delivery_rank(handoff.fulfillment_status)
        target_rank = self._delivery_rank(next_status)
        if target_rank <= current_rank:
            return
        await self._transition(handoff, next_status, expected_type="delivery")

    async def _transition(
        self,
        handoff: OpsCommerceOrder,
        status: FulfillmentStatus,
        *,
        expected_type: FulfillmentType,
    ) -> None:
        fulfillment_type = self._fulfillment_type(handoff)
        if fulfillment_type != expected_type:
            raise ConflictError("Storefront fulfilment type does not match the requested action")
        if status == handoff.fulfillment_status:
            return

        allowed_next = {
            "collection": {
                "confirmed": {"ready_for_collection", "cancelled"},
                "ready_for_collection": {"collected"},
            },
            "delivery": {
                # Existing deliveries can be packed/loaded before the Storefront
                # bridge is deployed. Their next staff action may be completion,
                # so record the current forward state without replaying each step.
                "confirmed": {
                    "ready_for_delivery",
                    "out_for_delivery",
                    "delivered",
                    "cancelled",
                },
                "ready_for_delivery": {"out_for_delivery", "delivered"},
                "out_for_delivery": {"delivered"},
            },
        }
        if status not in allowed_next[fulfillment_type].get(handoff.fulfillment_status, set()):
            raise ConflictError("Storefront fulfilment status cannot move backwards or skip a step")

        handoff.fulfillment_status = status
        handoff.fulfillment_revision += 1
        occurred_at = datetime.datetime.utcnow()
        promise = handoff.payload.get("fulfillment_promise")
        self.db.add(
            OpsCommerceFulfillmentEvent(
                id=uuid.uuid4(),
                company_id=handoff.company_id,
                handoff_id=handoff.id,
                external_order_id=handoff.external_order_id,
                revision=handoff.fulfillment_revision,
                fulfillment_type=fulfillment_type,
                status=status,
                fulfillment_promise=promise,
                occurred_at=occurred_at,
            )
        )
        await self.db.flush()

    @staticmethod
    def _fulfillment_type(handoff: OpsCommerceOrder) -> Optional[FulfillmentType]:
        value = handoff.payload.get("fulfillment", {}).get("type")
        return value if value in ("delivery", "collection") else None

    @staticmethod
    def _delivery_rank(status: str) -> int:
        return {
            "confirmed": 0,
            "ready_for_delivery": 1,
            "out_for_delivery": 2,
            "delivered": 3,
        }.get(status, -1)
