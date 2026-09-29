from __future__ import annotations

import hashlib
import hmac
import json
import logging
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.crud.location import LocationCRUD
from app.crud.ops_commerce import OpsCommerceCRUD
from app.crud.ops_commerce_orders import OpsCommerceOrdersCRUD
from app.crud.ops_commerce_fulfillment_events import OpsCommerceFulfillmentEventsCRUD
from app.crud.sales_order import SalesOrderCRUD
from app.crud.team_settings import TeamSettingsCRUD
from app.models.customer import Customer
from app.models.inventory import LocationStock
from app.models.journal import JournalDocumentType
from app.models.location import LocationType
from app.models.ops_commerce_acknowledgement import OpsCommerceAcknowledgement
from app.models.ops_commerce_order import OpsCommerceOrder
from app.models.sales_order import SalesOrder, SalesOrderLine, SalesOrderStatus
from app.models.sku import Sku
from app.models.team import Team
from app.models.user import User
from app.schemas.ops_commerce import OpsProductResponse, OpsProductsResponse
from app.schemas.ops_commerce_order import (
    StorefrontCollectionStatusUpdate,
    StorefrontFulfillmentEvent,
    StorefrontFulfillmentEventAckResponse,
    StorefrontFulfillmentEventList,
    StorefrontHandoffListResponse,
    StorefrontHandoffResponse,
    StorefrontPaidOrder,
)
from app.services.storefront_fulfillment import StorefrontFulfillmentService
from app.services.chart_of_accounts import (
    CODE_DEPOSITS,
    CODE_STOREFRONT_CLEARING,
    LedgerPostingService,
)
from app.services.sales_orders import SalesOrdersService
from app.services.storefront_system_actor import StorefrontSystemActorService
from app.services.vat import ex_to_inc
from app.models.unit_cost_audit import UnitCostAuditSource
from f0rge_core.exceptions import ConflictError, NotFoundError
from f0rge_db.crud import unit_of_work

logger = logging.getLogger(__name__)
CENT = Decimal("0.01")
ACTOR_LEASE = timedelta(minutes=2)


class OpsCommerceService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = OpsCommerceCRUD(db)
        self.orders = OpsCommerceOrdersCRUD(db)

    async def products(
        self,
        *,
        authorization: Optional[str],
        requested_company: Optional[str],
        request_host: str,
    ) -> OpsProductsResponse:
        company_id = await self._authorize(
            authorization=authorization,
            requested_company=requested_company,
            request_host=request_host,
        )
        snapshots = await self.crud.published_products()
        return OpsProductsResponse(
            company_id=company_id,
            products=[
                OpsProductResponse(
                    source_sku_id=sku.id,
                    sku=sku.sku,
                    name=sku.name,
                    price_minor_zar=int(ex_to_inc(sku.retail_ex_vat) * 100),
                    available_quantity=sku.available_quantity,
                    revision=self._utc_revision(sku.revision),
                    observed_at=self._as_utc(sku.observed_at),
                    product_group_id=sku.product_group_id,
                    product_title=sku.product_title,
                    options=sku.options,
                    acknowledged_commitment_ids=sku.acknowledged_commitment_ids,
                )
                for sku in snapshots
            ],
        )

    async def accept_paid_order(
        self,
        data: StorefrontPaidOrder,
        *,
        authorization: Optional[str],
        requested_company: Optional[str],
        request_host: str,
    ) -> tuple[StorefrontHandoffResponse, int]:
        company_id = await self._authorize(
            authorization=authorization,
            requested_company=requested_company,
            request_host=request_host,
        )
        if data.company_id != company_id:
            raise HTTPException(status_code=403, detail="Wrong operational company")

        payload = data.model_dump(mode="json")
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        existing = await self.orders.get_by_identity(
            company_id,
            data.channel,
            data.external_order_id,
        )
        if existing is not None:
            if not hmac.compare_digest(existing.payload_sha256, digest):
                raise HTTPException(
                    status_code=409, detail="Order identity was already used for another payload"
                )
            result = await self._attempt_import(existing.id)
            return result, 200 if result.status == "imported" else 202

        if await self.orders.payment_in_use(company_id, data.channel, data.external_payment_id):
            raise HTTPException(status_code=409, detail="Payment identity was already used")

        try:
            handoff = await self._record_paid_order(company_id, data, payload, digest)
        except IntegrityError:
            await self.db.rollback()
            existing = await self.orders.get_by_identity(
                company_id,
                data.channel,
                data.external_order_id,
            )
            if existing is not None and hmac.compare_digest(existing.payload_sha256, digest):
                result = await self._attempt_import(existing.id)
                return result, 200 if result.status == "imported" else 202
            if await self.orders.payment_in_use(company_id, data.channel, data.external_payment_id):
                raise HTTPException(status_code=409, detail="Payment identity was already used")
            raise

        result = await self._attempt_import(handoff.id)
        return result, 201 if result.status == "imported" else 202

    async def list_handoffs(self, staff_user_id: uuid.UUID) -> StorefrontHandoffListResponse:
        company_id = self._configured_company_id()
        await self._require_company_staff(staff_user_id, company_id)
        rows = await self.orders.list_latest(company_id)
        return StorefrontHandoffListResponse(items=[self._response(row) for row in rows])

    async def retry_handoff(
        self,
        handoff_id: uuid.UUID,
        staff_user_id: uuid.UUID,
    ) -> StorefrontHandoffResponse:
        company_id = self._configured_company_id()
        await self._require_company_staff(staff_user_id, company_id)
        handoff = await self.orders.get_by_id(handoff_id)
        if handoff is None or handoff.company_id != company_id:
            raise NotFoundError("Storefront handoff not found")
        return await self._attempt_import(handoff_id, requested_by_user_id=staff_user_id)

    async def update_collection_status(
        self,
        handoff_id: uuid.UUID,
        update: StorefrontCollectionStatusUpdate,
        staff_user_id: uuid.UUID,
    ) -> StorefrontHandoffResponse:
        company_id = self._configured_company_id()
        await self._require_company_staff(staff_user_id, company_id)
        handoff = await self.orders.get_by_id(handoff_id)
        if handoff is None or handoff.company_id != company_id:
            raise NotFoundError("Storefront order not found")
        updated = await StorefrontFulfillmentService(self.db).update_collection_status(
            handoff_id, update.status
        )
        return self._response(updated)

    async def list_fulfillment_events(
        self,
        *,
        authorization: Optional[str],
        requested_company: Optional[str],
        request_host: str,
        limit: int = 100,
    ) -> StorefrontFulfillmentEventList:
        company_id = await self._authorize(
            authorization=authorization,
            requested_company=requested_company,
            request_host=request_host,
        )
        rows = await OpsCommerceFulfillmentEventsCRUD(self.db).pending_for_company(
            company_id, limit=limit
        )
        return StorefrontFulfillmentEventList(
            items=[
                StorefrontFulfillmentEvent(
                    event_id=row.id,
                    company_id=row.company_id,
                    external_order_id=row.external_order_id,
                    revision=row.revision,
                    fulfillment_type=row.fulfillment_type,
                    status=row.status,
                    fulfillment_promise=row.fulfillment_promise,
                    occurred_at=row.occurred_at,
                )
                for row in rows
            ]
        )

    async def acknowledge_fulfillment_events(
        self,
        event_ids: list[uuid.UUID],
        *,
        authorization: Optional[str],
        requested_company: Optional[str],
        request_host: str,
    ) -> StorefrontFulfillmentEventAckResponse:
        company_id = await self._authorize(
            authorization=authorization,
            requested_company=requested_company,
            request_host=request_host,
        )
        async with unit_of_work(self.db):
            acknowledged = await OpsCommerceFulfillmentEventsCRUD(self.db).acknowledge(
                company_id, event_ids
            )
        return StorefrontFulfillmentEventAckResponse(acknowledged=acknowledged)

    async def _require_company_staff(
        self,
        staff_user_id: uuid.UUID,
        company_id: uuid.UUID,
    ) -> None:
        staff = await self.db.get(User, staff_user_id)
        if (
            staff is None
            or staff.team_id != company_id
            or staff.is_disabled
            or staff.role == "system"
        ):
            raise HTTPException(
                status_code=403, detail="Storefront orders are not available to this user"
            )

    async def _record_paid_order(
        self,
        company_id: uuid.UUID,
        data: StorefrontPaidOrder,
        payload: dict[str, object],
        digest: str,
    ) -> OpsCommerceOrder:
        team = await self.db.get(Team, company_id)
        if team is None:
            raise HTTPException(status_code=503, detail="Operational company is unavailable")

        sku_ids = [line.source_sku_id for line in data.lines]
        skus = list(
            (await self.db.execute(select(Sku).where(Sku.id.in_(sku_ids)).order_by(Sku.id)))
            .scalars()
            .all()
        )
        by_id = {sku.id: sku for sku in skus}
        for line in data.lines:
            source_sku = by_id.get(line.source_sku_id)
            if source_sku is None or source_sku.our_ref != line.sku:
                raise HTTPException(
                    status_code=409, detail="An order item no longer matches its operational SKU"
                )

        customer = await self.db.scalar(
            select(Customer).where(func.lower(Customer.email) == data.customer.email.lower())
        )
        if customer is None:
            customer = Customer(
                name=data.customer.name,
                email=data.customer.email,
                phone=data.customer.phone,
                billing_address=data.customer.billing_address or None,
            )
            self.db.add(customer)
            await self.db.flush()

        location_id = await self._preferred_location(company_id)
        money = self._money
        order_total = money(data.totals.total_minor_zar)
        order = SalesOrder(
            so_number="",
            customer_id=customer.id,
            location_id=location_id,
            hold_stock=False,
            awaiting_stock=True,
            status=SalesOrderStatus.AWAITING_STOCK,
            subtotal_ex_vat=money(
                data.totals.subtotal_ex_minor_zar + data.totals.delivery_ex_minor_zar
            ),
            vat_amount=money(data.totals.tax_minor_zar),
            total_inc_vat=order_total,
            amount_paid=order_total,
            fulfillment_promise=(
                data.fulfillment_promise.model_dump(mode="json")
                if data.fulfillment_promise is not None
                else None
            ),
            notes=f"Storefront order {data.external_order_id}; delivery {data.fulfillment.reference}",
            lines=[
                SalesOrderLine(
                    sku_id=line.source_sku_id,
                    qty=line.quantity,
                    unit_ex_vat=money(line.unit_ex_minor_zar),
                    description=line.title,
                    notes=f"Storefront line {line.external_line_id}",
                    fulfillment_promise=(
                        line.fulfillment_promise.model_dump(mode="json")
                        if line.fulfillment_promise is not None
                        else None
                    ),
                    held_qty=0,
                )
                for line in data.lines
            ],
        )
        sales_crud = SalesOrderCRUD(self.db)
        async with unit_of_work(self.db):
            order.so_number = await sales_crud.get_next_so_number()
            await sales_crud.add_and_flush(order)
            handoff_id = uuid.uuid4()
            payment = await LedgerPostingService(self.db).post(
                JournalDocumentType.PAYMENT,
                handoff_id,
                f"Storefront captured payment {data.external_order_id}",
                [
                    (CODE_STOREFRONT_CLEARING, order_total, Decimal(0)),
                    (CODE_DEPOSITS, Decimal(0), order_total),
                ],
                entry_date=data.payment.captured_at.date(),
                source="storefront",
            )
            handoff = OpsCommerceOrder(
                id=handoff_id,
                company_id=company_id,
                channel=data.channel,
                external_order_id=data.external_order_id,
                external_payment_id=data.external_payment_id,
                gateway_provider=data.payment.provider,
                gateway_reference=data.payment.reference,
                currency_code=data.currency_code,
                captured_amount_minor=data.payment.amount_minor_zar,
                payload_sha256=digest,
                payload=payload,
                correlation_id=data.correlation_id,
                status="pending",
                attempt_count=0,
                sales_order_id=order.id,
                payment_journal_id=payment.id,
            )
            self.db.add(handoff)
            await self.db.flush()
        return handoff

    async def _attempt_import(
        self,
        handoff_id: uuid.UUID,
        *,
        requested_by_user_id: Optional[uuid.UUID] = None,
    ) -> StorefrontHandoffResponse:
        now = datetime.utcnow()
        async with unit_of_work(self.db):
            handoff = await self.orders.get_by_id(handoff_id, for_update=True)
            if handoff is None:
                raise NotFoundError("Storefront handoff not found")
            if handoff.status == "imported":
                return self._response(handoff)
            if (
                handoff.status == "processing"
                and handoff.last_attempt_at is not None
                and handoff.last_attempt_at > now - ACTOR_LEASE
            ):
                return self._response(handoff)
            handoff.status = "processing"
            handoff.failure_code = None
            handoff.attempt_count += 1
            handoff.last_attempt_at = now

        payload = StorefrontPaidOrder.model_validate(handoff.payload)
        location_id = await self._available_location(payload)
        if location_id is None:
            await self._finish_failed(handoff_id, status="stock_conflict", code="stock_unavailable")
            return await self._response_for(handoff_id)

        sales_order = await SalesOrderCRUD(self.db).get_by_id(handoff.sales_order_id)
        if sales_order is None:
            await self._finish_failed(handoff_id, status="failed", code="sales_order_missing")
            return await self._response_for(handoff_id)
        async with unit_of_work(self.db):
            sales_order.location_id = location_id
            sales_order.awaiting_stock = True

        actor = await StorefrontSystemActorService(self.db).ensure(handoff.company_id)
        actor_id = requested_by_user_id or actor.id
        money = self._money
        invoice_tax_snapshot = [
            (money(line.ex_minor_zar), money(line.vat_minor_zar), money(line.total_minor_zar))
            for line in payload.lines
        ]
        invoice_tax_snapshot.append(
            (
                money(payload.totals.delivery_ex_minor_zar),
                money(payload.totals.delivery_tax_minor_zar),
                money(payload.totals.delivery_total_minor_zar),
            )
        )

        async def record_acknowledgements() -> None:
            for line in payload.lines:
                self.db.add(
                    OpsCommerceAcknowledgement(
                        commitment_id=(
                            f"storefront:{payload.external_order_id}:{line.external_line_id}"
                        ),
                        source_sku_id=line.source_sku_id,
                        quantity=line.quantity,
                    )
                )
            current = await self.orders.get_by_id(handoff_id, for_update=True)
            if current is None:
                raise NotFoundError("Storefront handoff not found")
            current.status = "imported"
            current.failure_code = None
            current.imported_at = datetime.utcnow()

        try:
            await SalesOrdersService(self.db).create_remainder_invoice(
                sales_order.id,
                actor_id,
                tax_snapshot=invoice_tax_snapshot,
                stock_source=UnitCostAuditSource.STOREFRONT,
                before_commit=record_acknowledgements,
            )
        except ConflictError as exc:
            if str(exc) == "Insufficient on-hand quantity":
                await self._finish_failed(
                    handoff_id, status="stock_conflict", code="stock_unavailable"
                )
                return await self._response_for(handoff_id)
            await self._finish_failed(
                handoff_id, status="failed", code="inventory_or_period_conflict"
            )
            logger.warning(
                "Storefront handoff %s blocked by a domain conflict", handoff.correlation_id
            )
            return await self._response_for(handoff_id)
        except Exception as exc:
            await self._finish_failed(handoff_id, status="failed", code="handoff_processing_failed")
            logger.warning(
                "Storefront handoff %s failed (%s)", handoff.correlation_id, type(exc).__name__
            )
            return await self._response_for(handoff_id)
        return await self._response_for(handoff_id)

    async def _available_location(self, data: StorefrontPaidOrder) -> Optional[uuid.UUID]:
        company_id = data.company_id
        locations = [
            location
            for location in await LocationCRUD(self.db).list_all()
            if not location.is_archived
            and location.type in (LocationType.WAREHOUSE, LocationType.SHOWROOM)
        ]
        team_settings = await TeamSettingsCRUD(self.db).get_by_team_id(company_id)
        preferred_id = team_settings.default_receive_location_id if team_settings else None
        locations.sort(key=lambda loc: (loc.id != preferred_id, loc.name.casefold()))
        required: dict[uuid.UUID, int] = defaultdict(int)
        for line in data.lines:
            required[line.source_sku_id] += line.quantity
        for location in locations:
            result = await self.db.execute(
                select(LocationStock.sku_id, LocationStock.on_hand).where(
                    LocationStock.location_id == location.id,
                    LocationStock.sku_id.in_(required),
                )
            )
            available = {sku_id: qty for sku_id, qty in result.all()}
            if all(available.get(sku_id, 0) >= quantity for sku_id, quantity in required.items()):
                return location.id
        return None

    async def _preferred_location(self, company_id: uuid.UUID) -> Optional[uuid.UUID]:
        team_settings = await TeamSettingsCRUD(self.db).get_by_team_id(company_id)
        preferred_id = team_settings.default_receive_location_id if team_settings else None
        locations = [
            location
            for location in await LocationCRUD(self.db).list_all()
            if not location.is_archived
            and location.type in (LocationType.WAREHOUSE, LocationType.SHOWROOM)
        ]
        locations.sort(key=lambda loc: (loc.id != preferred_id, loc.name.casefold()))
        return locations[0].id if locations else None

    async def _finish_failed(self, handoff_id: uuid.UUID, *, status: str, code: str) -> None:
        async with unit_of_work(self.db):
            handoff = await self.orders.get_by_id(handoff_id, for_update=True)
            if handoff is None or handoff.status == "imported":
                return
            handoff.status = status
            handoff.failure_code = code

    async def _response_for(self, handoff_id: uuid.UUID) -> StorefrontHandoffResponse:
        handoff = await self.orders.get_by_id(handoff_id)
        if handoff is None:
            raise NotFoundError("Storefront handoff not found")
        return self._response(handoff)

    async def _authorize(
        self,
        *,
        authorization: Optional[str],
        requested_company: Optional[str],
        request_host: str,
    ) -> uuid.UUID:
        company_id = self._configured_company_id()
        expected = f"Bearer {settings.ops_commerce_token}"
        if not authorization or not hmac.compare_digest(authorization, expected):
            raise HTTPException(status_code=401, detail="Invalid service credential")
        if request_host != settings.ops_commerce_allowed_host:
            raise HTTPException(status_code=403, detail="Wrong operational host")
        if requested_company != str(company_id):
            raise HTTPException(status_code=403, detail="Wrong operational company")
        if not await self.crud.has_company(company_id):
            raise HTTPException(status_code=503, detail="Operational company is unavailable")
        return company_id

    @staticmethod
    def _configured_company_id() -> uuid.UUID:
        if (
            not settings.ops_commerce_token
            or not settings.ops_commerce_company_id
            or not settings.ops_commerce_allowed_host
        ):
            raise HTTPException(status_code=503, detail="Ops Commerce is not configured")
        try:
            return uuid.UUID(settings.ops_commerce_company_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=503, detail="Invalid Ops Commerce configuration"
            ) from exc

    @staticmethod
    def _money(minor: int) -> Decimal:
        return (Decimal(minor) / Decimal(100)).quantize(CENT)

    @staticmethod
    def _response(row: OpsCommerceOrder) -> StorefrontHandoffResponse:
        fulfillment = row.payload.get("fulfillment", {})
        return StorefrontHandoffResponse(
            id=row.id,
            external_order_id=row.external_order_id,
            correlation_id=row.correlation_id,
            status=row.status,
            failure_code=row.failure_code,
            attempt_count=row.attempt_count,
            last_attempt_at=row.last_attempt_at,
            imported_at=row.imported_at,
            sales_order_id=row.sales_order_id,
            payment_journal_id=row.payment_journal_id,
            fulfillment_type=fulfillment.get("type", "delivery"),
            fulfillment_status=row.fulfillment_status,
            fulfillment_revision=row.fulfillment_revision,
            fulfillment_promise=row.payload.get("fulfillment_promise"),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        return (
            value.replace(tzinfo=timezone.utc)
            if value.tzinfo is None
            else value.astimezone(timezone.utc)
        )

    @classmethod
    def _utc_revision(cls, value: datetime) -> str:
        return cls._as_utc(value).isoformat(timespec="microseconds").replace("+00:00", "Z")
