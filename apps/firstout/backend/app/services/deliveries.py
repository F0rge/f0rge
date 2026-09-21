from __future__ import annotations

import datetime
import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.delivery import DeliveryCRUD
from app.crud.layby import LaybyCRUD
from app.crud.location import LocationCRUD
from app.crud.sales_order import SalesOrderCRUD
from app.crud.sku import SkuCRUD
from app.crud.tax_invoice import TaxInvoiceCRUD
from app.models.delivery import (
    Delivery,
    DeliveryLine,
    DeliverySourceType,
    DeliveryStatus,
)
from app.models.layby import LaybyStatus
from app.models.sales_order import SalesOrderStatus
from app.models.tax_invoice import InvoiceLine
from app.schemas.delivery import (
    DeliveryComplete,
    DeliveryCreate,
    DeliveryLineResponse,
    DeliveryListItem,
    DeliveryPack,
    DeliveryResponse,
    DeliveryTrackingUpdate,
)
from app.schemas.page import Page, PageParams
from f0rge_core.exceptions import ConflictError, NotFoundError, ValidationError
from f0rge_db.crud import unit_of_work


class DeliveriesService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = DeliveryCRUD(db)
        self.invoice_crud = TaxInvoiceCRUD(db)
        self.layby_crud = LaybyCRUD(db)
        self.sales_order_crud = SalesOrderCRUD(db)
        self.location_crud = LocationCRUD(db)
        self.sku_crud = SkuCRUD(db)

    async def list(
        self,
        params: PageParams,
        status: Optional[DeliveryStatus] = None,
    ) -> Page[DeliveryListItem]:
        rows, total = await self.crud.list_page(
            limit=params.limit,
            offset=params.offset,
            q=params.q,
            status=status,
        )
        return Page(
            items=[self._to_list_item(row) for row in rows],
            total=total,
        )

    async def get(self, delivery_id: uuid.UUID) -> DeliveryResponse:
        return self._to_response(await self._get_or_404(delivery_id))

    async def create(
        self,
        data: DeliveryCreate,
        user_id: uuid.UUID,
        lines_override: Optional[list[DeliveryLine]] = None,
    ) -> DeliveryResponse:
        location = await self.location_crud.get_by_id(data.location_id)
        if location is None:
            raise NotFoundError("Location not found")
        if location.is_archived:
            raise ConflictError("Cannot deliver from archived location")

        if data.source_type == DeliverySourceType.INVOICE:
            assert data.invoice_id is not None
            delivery = await self._create_from_invoice(
                data,
                user_id,
                lines_override,
                delivery_number="",
            )
        elif data.source_type == DeliverySourceType.LAYBY:
            assert data.layby_id is not None
            delivery = await self._create_from_layby(
                data,
                user_id,
                lines_override,
                delivery_number="",
            )
        else:
            assert data.sales_order_id is not None
            delivery = await self._create_from_sales_order(
                data,
                user_id,
                lines_override,
                delivery_number="",
            )

        async with unit_of_work(self.db):
            delivery.delivery_number = await self.crud.get_next_delivery_number()
            await self.crud.add_and_flush(delivery)

        return self._to_response(await self._get_or_404(delivery.id))

    async def pack(
        self,
        delivery_id: uuid.UUID,
        body: Optional[DeliveryPack] = None,
    ) -> DeliveryResponse:
        delivery = await self._get_or_404(delivery_id)
        if delivery.status != DeliveryStatus.DRAFT:
            raise ConflictError("Delivery is not a draft")
        async with unit_of_work(self.db):
            delivery.status = DeliveryStatus.PACKED
            if body is not None and body.carton_count is not None:
                delivery.carton_count = body.carton_count
        return self._to_response(await self._get_or_404(delivery_id))

    async def load(self, delivery_id: uuid.UUID) -> DeliveryResponse:
        delivery = await self._get_or_404(delivery_id)
        if delivery.status != DeliveryStatus.PACKED:
            raise ConflictError("Delivery is not packed")
        async with unit_of_work(self.db):
            delivery.status = DeliveryStatus.LOADED
            delivery.loaded_at = datetime.datetime.utcnow()
        return self._to_response(await self._get_or_404(delivery_id))

    async def update_tracking(
        self,
        delivery_id: uuid.UUID,
        body: DeliveryTrackingUpdate,
    ) -> DeliveryResponse:
        delivery = await self._get_or_404(delivery_id)
        if delivery.status in (DeliveryStatus.CANCELLED, DeliveryStatus.DELIVERED):
            raise ConflictError("Cannot update tracking on this delivery")
        async with unit_of_work(self.db):
            if body.tracking_number is not None:
                delivery.tracking_number = body.tracking_number
            if body.carrier is not None:
                delivery.carrier = body.carrier
        return self._to_response(await self._get_or_404(delivery_id))

    async def complete(
        self,
        delivery_id: uuid.UUID,
        body: DeliveryComplete,
    ) -> DeliveryResponse:
        delivery = await self._get_or_404(delivery_id)
        if delivery.status not in (DeliveryStatus.PACKED, DeliveryStatus.LOADED):
            raise ConflictError("Delivery is not packed")
        delivery_date = body.delivery_date or datetime.date.today()
        async with unit_of_work(self.db):
            delivery.status = DeliveryStatus.DELIVERED
            delivery.delivery_date = delivery_date
            if body.tracking_number is not None:
                delivery.tracking_number = body.tracking_number
            if body.carrier is not None:
                delivery.carrier = body.carrier
        return self._to_response(await self._get_or_404(delivery_id))

    async def cancel(self, delivery_id: uuid.UUID) -> DeliveryResponse:
        delivery = await self._get_or_404(delivery_id)
        if delivery.status != DeliveryStatus.DRAFT:
            raise ConflictError("Delivery is not a draft")
        async with unit_of_work(self.db):
            delivery.status = DeliveryStatus.CANCELLED
        return self._to_response(await self._get_or_404(delivery_id))

    async def _create_from_invoice(
        self,
        data: DeliveryCreate,
        user_id: uuid.UUID,
        lines_override: Optional[list[DeliveryLine]] = None,
        *,
        delivery_number: str,
    ) -> Delivery:
        invoice = await self.invoice_crud.get_by_id(data.invoice_id)
        if invoice is None:
            raise NotFoundError("Invoice not found")
        if invoice.amount_paid != invoice.total_inc_vat:
            raise ValidationError("Invoice is not fully paid")

        existing = await self.crud.get_active_by_invoice_id(invoice.id)
        if existing is not None:
            raise ConflictError("Delivery already exists for this invoice")

        sku_ids = [line.sku_id for line in invoice.lines if line.sku_id is not None]
        skus_by_id = await self._load_skus(sku_ids)
        lines = (
            lines_override
            if lines_override is not None
            else self._lines_from_invoice(invoice.lines, skus_by_id)
        )

        return Delivery(
            delivery_number=delivery_number,
            source_type=DeliverySourceType.INVOICE,
            invoice_id=invoice.id,
            layby_id=None,
            sales_order_id=None,
            location_id=data.location_id,
            status=DeliveryStatus.DRAFT,
            notes=data.notes,
            created_by_user_id=user_id,
            lines=lines,
        )

    async def _create_from_layby(
        self,
        data: DeliveryCreate,
        user_id: uuid.UUID,
        lines_override: Optional[list[DeliveryLine]] = None,
        *,
        delivery_number: str,
    ) -> Delivery:
        layby = await self.layby_crud.get_by_id(data.layby_id)
        if layby is None:
            raise NotFoundError("Layby not found")
        if layby.status == LaybyStatus.CANCELLED:
            raise ConflictError("Layby is cancelled")

        existing = await self.crud.get_active_by_layby_id(layby.id)
        if existing is not None:
            raise ConflictError("Delivery already exists for this layby")

        lines = (
            lines_override if lines_override is not None else self._lines_from_layby(layby.lines)
        )
        return Delivery(
            delivery_number=delivery_number,
            source_type=DeliverySourceType.LAYBY,
            invoice_id=None,
            layby_id=layby.id,
            sales_order_id=None,
            location_id=data.location_id,
            status=DeliveryStatus.DRAFT,
            notes=data.notes,
            created_by_user_id=user_id,
            lines=lines,
        )

    async def _create_from_sales_order(
        self,
        data: DeliveryCreate,
        user_id: uuid.UUID,
        lines_override: Optional[list[DeliveryLine]] = None,
        *,
        delivery_number: str,
    ) -> Delivery:
        order = await self.sales_order_crud.get_by_id(data.sales_order_id)
        if order is None:
            raise NotFoundError("Sales order not found")
        if order.status == SalesOrderStatus.CANCELLED:
            raise ConflictError("Sales order is cancelled")

        existing = await self.crud.get_active_by_sales_order_id(order.id)
        if existing is not None:
            raise ConflictError("Delivery already exists for this sales order")

        lines = (
            lines_override
            if lines_override is not None
            else self._lines_from_sales_order(order.lines)
        )
        return Delivery(
            delivery_number=delivery_number,
            source_type=DeliverySourceType.SALES_ORDER,
            invoice_id=None,
            layby_id=None,
            sales_order_id=order.id,
            location_id=data.location_id,
            status=DeliveryStatus.DRAFT,
            notes=data.notes,
            created_by_user_id=user_id,
            lines=lines,
        )

    async def _load_skus(self, sku_ids: list[uuid.UUID]) -> dict[uuid.UUID, Sku]:
        skus_by_id: dict[uuid.UUID, Sku] = {}
        for sku_id in sku_ids:
            sku = await self.sku_crud.get_by_id(sku_id)
            if sku is not None:
                skus_by_id[sku_id] = sku
        return skus_by_id

    @staticmethod
    def _lines_from_invoice(
        invoice_lines: list[InvoiceLine],
        skus_by_id: dict[uuid.UUID, Sku],
    ) -> list[DeliveryLine]:
        models: list[DeliveryLine] = []
        for sort_order, line in enumerate(invoice_lines):
            sku = skus_by_id.get(line.sku_id) if line.sku_id is not None else None
            models.append(
                DeliveryLine(
                    sku_id=line.sku_id,
                    description=DeliveriesService._invoice_line_description(line, sku),
                    qty=line.qty,
                    sort_order=sort_order,
                )
            )
        return models

    @staticmethod
    def _lines_from_layby(layby_lines: list) -> list[DeliveryLine]:
        models: list[DeliveryLine] = []
        for sort_order, line in enumerate(layby_lines):
            sku = line.sku
            description = sku.name if sku.name else sku.our_ref
            models.append(
                DeliveryLine(
                    sku_id=line.sku_id,
                    description=description,
                    qty=line.qty,
                    sort_order=sort_order,
                )
            )
        return models

    @staticmethod
    def _lines_from_sales_order(order_lines: list) -> list[DeliveryLine]:
        models: list[DeliveryLine] = []
        for sort_order, line in enumerate(order_lines):
            sku = line.sku
            description = line.description or (sku.name if sku.name else sku.our_ref)
            models.append(
                DeliveryLine(
                    sku_id=line.sku_id,
                    description=description,
                    qty=line.qty,
                    sort_order=sort_order,
                )
            )
        return models

    @staticmethod
    def _invoice_line_description(line: InvoiceLine, sku: Optional[Sku]) -> str:
        if line.description and line.description.strip():
            return line.description
        if sku is not None:
            return sku.name if sku.name else sku.our_ref
        return line.description

    async def _get_or_404(self, delivery_id: uuid.UUID) -> Delivery:
        delivery = await self.crud.get_by_id(delivery_id)
        if delivery is None:
            raise NotFoundError("Delivery not found")
        return delivery

    def _source_fields(
        self, delivery: Delivery
    ) -> tuple[str, Optional[str], Optional[str], Optional[str]]:
        customer_name = ""
        invoice_number: Optional[str] = None
        layby_number: Optional[str] = None
        so_number: Optional[str] = None
        if delivery.source_type == DeliverySourceType.INVOICE and delivery.invoice is not None:
            customer_name = delivery.invoice.customer.name
            invoice_number = delivery.invoice.invoice_number
        elif delivery.source_type == DeliverySourceType.LAYBY and delivery.layby is not None:
            customer_name = delivery.layby.customer.name
            layby_number = delivery.layby.layby_number
        elif (
            delivery.source_type == DeliverySourceType.SALES_ORDER
            and delivery.sales_order is not None
        ):
            customer_name = delivery.sales_order.customer.name
            so_number = delivery.sales_order.so_number
        return customer_name, invoice_number, layby_number, so_number

    def _to_list_item(self, delivery: Delivery) -> DeliveryListItem:
        customer_name, invoice_number, layby_number, so_number = self._source_fields(delivery)
        return DeliveryListItem(
            id=delivery.id,
            delivery_number=delivery.delivery_number,
            source_type=delivery.source_type,
            invoice_id=delivery.invoice_id,
            invoice_number=invoice_number,
            layby_id=delivery.layby_id,
            layby_number=layby_number,
            sales_order_id=delivery.sales_order_id,
            so_number=so_number,
            customer_name=customer_name,
            location_id=delivery.location_id,
            location_name=delivery.location.name,
            status=delivery.status,
            delivery_date=delivery.delivery_date,
            carton_count=delivery.carton_count,
            loaded_at=delivery.loaded_at,
            tracking_number=delivery.tracking_number,
            carrier=delivery.carrier,
            notes=delivery.notes,
            created_at=delivery.created_at,
            updated_at=delivery.updated_at,
        )

    def _to_response(self, delivery: Delivery) -> DeliveryResponse:
        customer_name, invoice_number, layby_number, so_number = self._source_fields(delivery)
        return DeliveryResponse(
            id=delivery.id,
            delivery_number=delivery.delivery_number,
            source_type=delivery.source_type,
            invoice_id=delivery.invoice_id,
            invoice_number=invoice_number,
            layby_id=delivery.layby_id,
            layby_number=layby_number,
            sales_order_id=delivery.sales_order_id,
            so_number=so_number,
            customer_name=customer_name,
            location_id=delivery.location_id,
            location_name=delivery.location.name,
            status=delivery.status,
            delivery_date=delivery.delivery_date,
            carton_count=delivery.carton_count,
            loaded_at=delivery.loaded_at,
            tracking_number=delivery.tracking_number,
            carrier=delivery.carrier,
            notes=delivery.notes,
            lines=[
                DeliveryLineResponse(
                    id=line.id,
                    sku_id=line.sku_id,
                    description=line.description,
                    qty=line.qty,
                )
                for line in delivery.lines
            ],
            created_at=delivery.created_at,
            updated_at=delivery.updated_at,
        )
