from __future__ import annotations

import datetime
import uuid
from collections import defaultdict
from decimal import Decimal
from io import BytesIO
from typing import TYPE_CHECKING, Optional

from fastapi import UploadFile
from sqlalchemy import func, select, update

from app.crud.bill import BillCRUD
from app.crud.purchase_order import LocationStockCRUD, PurchaseOrderCRUD
from app.crud.transfer import TransferCRUD
from app.models.inventory import LocationStock
from app.models.layby import Layby
from app.models.payment import Payment
from app.models.tax_invoice import InvoiceLine, TaxInvoice
from app.schemas.bill import BillCreate, BillLineCreate
from app.schemas.customer_crm import CustomerCrmCreate
from app.schemas.invoice import InvoiceCreate, InvoiceLineCreate
from app.schemas.layby import LaybyCreate, LaybyLineCreate, LaybyPaymentCreate
from app.schemas.payment import PaymentCreate
from app.schemas.purchase_order import PoLineCreate, PurchaseOrderCreate, ReceiveRequest
from app.schemas.sku import SkuCreate, SkuUpdate
from app.schemas.supplier import SupplierCreate
from app.schemas.till import TillSaleCreate, TillSaleLineCreate
from app.schemas.transfer import (
    TransferCreate,
    TransferLineCreate,
    TransferReceive,
    TransferReceiveLine,
)
from app.services.bills import BillService
from app.services.customers_crm import CustomersCrmService
from app.services.invoices import InvoiceService
from app.services.laybys import LaybysService
from app.services.locations import LocationSeedService
from app.services.payments import PaymentService
from app.services.playground_bi_catalog import (
    BI_CUSTOMERS,
    BI_MARKER_REF,
    BI_PACK_NOTES_PREFIX,
    BI_SKUS,
    BI_SUPPLIERS,
    lead_days_for,
    po_waves,
    pricing_for_role,
    qty_for_role,
    sku_barcode,
)
from app.services.purchase_orders import PurchaseOrderService
from app.services.skus import SkuService
from app.services.suppliers import SupplierService
from app.services.till_orchestrator import TillOrchestrator
from app.services.transfers import TransferService
from app.services.vat import CENT, ex_to_inc
from f0rge_core.exceptions import NotFoundError
from f0rge_db.crud import unit_of_work

if TYPE_CHECKING:
    from app.services.playground_seed import PlaygroundSeedService

EUR_FX = Decimal("19.50")


def _pdf_upload(filename: str) -> UploadFile:
    from app.services.playground_seed import MINIMAL_PDF

    return UploadFile(file=BytesIO(MINIMAL_PDF), filename=filename)


def _utc(days_ago: int) -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days_ago)


def _naive_utc(days_ago: int) -> datetime.datetime:
    return datetime.datetime.utcnow() - datetime.timedelta(days=days_ago)


class PlaygroundBiPack:
    def __init__(self, seed: PlaygroundSeedService) -> None:
        self.seed = seed
        self.db = seed.db
        self.warehouse: dict[str, int] = defaultdict(int)
        self.showroom: dict[str, int] = defaultdict(int)
        self.first_received_ago: dict[str, int] = {}
        self.showroom_since_ago: dict[str, int] = {}

    async def seed_if_needed(self) -> None:
        from app.config import settings

        owner = await self.seed.user_crud.get_by_email(settings.seed_owner_email)
        if owner is None:
            raise NotFoundError("Owner user not found for playground BI pack")

        kramerville = await self.seed._location_by_name(LocationSeedService.SEED_ROWS[0][0])
        bedfordview = await self.seed._location_by_name(LocationSeedService.SEED_ROWS[1][0])
        today = datetime.date.today()

        suppliers = await self._ensure_suppliers()
        customers = await self._ensure_customers()
        marker = await self.seed.sku_crud.get_by_our_ref(BI_MARKER_REF)
        if marker is None:
            skus = await self._create_skus(owner.id, suppliers)
            await self._seed_purchase_orders(owner.id, kramerville.id, suppliers, skus)
            await self._seed_transfers(owner.id, kramerville.id, bedfordview.id, skus)
            await self._seed_till_sales(bedfordview.id, customers, skus, today)
        else:
            skus = await self._existing_skus()
            if len(skus) < len(BI_SKUS):
                return
            await self._hydrate_showroom_from_stock(bedfordview.id, skus)
        await self._seed_invoices(customers, today)
        await self._seed_laybys(owner.id, bedfordview.id, customers, skus, today)
        await self._seed_bills(suppliers, today)
        await self._age_dead_stock(kramerville.id, skus)

    async def _ensure_suppliers(self) -> dict[str, uuid.UUID]:
        supplier_service = SupplierService(self.db)
        out: dict[str, uuid.UUID] = {}
        for spec in BI_SUPPLIERS:
            existing = await self.seed.supplier_crud.get_by_name_insensitive(spec["name"])
            if existing is None:
                await self.seed._ensure_transaction()
                created = await supplier_service.create(
                    SupplierCreate(name=spec["name"], default_currency=spec["default_currency"])
                )
                out[spec["key"]] = created.id
            else:
                out[spec["key"]] = existing.id
        return out

    async def _ensure_customers(self) -> dict[str, uuid.UUID]:
        crm = CustomersCrmService(self.db)
        out: dict[str, uuid.UUID] = {}
        for spec in BI_CUSTOMERS:
            existing = await self.seed._customer_by_name_insensitive(spec["name"])
            if existing is None:
                await self.seed._ensure_transaction()
                created = await crm.create(
                    CustomerCrmCreate(
                        name=spec["name"],
                        email=spec["email"],
                        phone=spec["phone"],
                        customer_type=spec["customer_type"],  # type: ignore[arg-type]
                        price_tier=spec["price_tier"],
                        vat_number=spec["vat_number"],
                        billing_address=spec["billing_address"],
                    )
                )
                out[spec["name"]] = created.id
            else:
                out[spec["name"]] = existing.id
        return out

    async def _existing_skus(self) -> dict[str, uuid.UUID]:
        out: dict[str, uuid.UUID] = {}
        for spec in BI_SKUS:
            row = await self.seed.sku_crud.get_by_our_ref(spec["our_ref"])
            if row is not None:
                out[spec["our_ref"]] = row.id
        return out

    async def _hydrate_showroom_from_stock(
        self,
        showroom_id: uuid.UUID,
        skus: dict[str, uuid.UUID],
    ) -> None:
        stock_crud = LocationStockCRUD(self.db)
        for ref, sku_id in skus.items():
            row = await stock_crud.get_by_sku_and_location(sku_id, showroom_id)
            self.showroom[ref] = int(row.on_hand) if row is not None else 0

    async def _count_bi_invoices(self) -> int:
        result = await self.db.execute(
            select(func.count(func.distinct(InvoiceLine.invoice_id))).where(
                InvoiceLine.description.startswith(BI_PACK_NOTES_PREFIX)
            )
        )
        return int(result.scalar_one() or 0)

    async def _count_bi_laybys(self) -> int:
        result = await self.db.execute(
            select(func.count())
            .select_from(Layby)
            .where(Layby.notes.startswith(BI_PACK_NOTES_PREFIX))
        )
        return int(result.scalar_one() or 0)

    async def _stamp_partial_balance(self, invoice_id: uuid.UUID) -> None:
        await self.seed._ensure_transaction()
        async with unit_of_work(self.db):
            invoice = await self.db.get(TaxInvoice, invoice_id)
            if invoice is None or invoice.amount_paid != 0:
                return
            part = (invoice.total_inc_vat * Decimal("0.40")).quantize(CENT)
            if 0 < part < invoice.total_inc_vat:
                invoice.amount_paid = part

    async def _backfill_partial_balances(self) -> None:
        dining = f"{BI_PACK_NOTES_PREFIX} trade dining specification"
        result = await self.db.execute(
            select(InvoiceLine.invoice_id).where(InvoiceLine.description == dining)
        )
        for invoice_id in {row[0] for row in result.all()}:
            await self._stamp_partial_balance(invoice_id)

    async def _create_skus(
        self,
        owner_id: uuid.UUID,
        suppliers: dict[str, uuid.UUID],
    ) -> dict[str, uuid.UUID]:
        sku_service = SkuService(self.db)
        out: dict[str, uuid.UUID] = {}
        for index, spec in enumerate(BI_SKUS, start=1):
            retail = Decimal(spec["retail_ex"])
            wholesale, _unit_cost = pricing_for_role(retail, spec["role"])
            photo = self._resolve_photo(spec["photo"])
            lead = lead_days_for(spec["supplier_key"], spec["category"])
            await self.seed._ensure_transaction()
            created = await sku_service.create(
                SkuCreate(
                    our_ref=spec["our_ref"],
                    our_barcode=sku_barcode(index),
                    name=spec["name"],
                    design=spec["design"],
                    fabric=spec["fabric"],
                    category=spec["category"],
                    supplier_ref=spec["supplier_ref"],
                ),
                owner_id,
            )
            sku_update = SkuUpdate(
                retail_ex_vat=retail,
                wholesale_ex_vat=wholesale,
                category=spec["category"],
                preferred_supplier_id=suppliers[spec["supplier_key"]],
                lead_time_days=lead,
                supplier_ref=spec["supplier_ref"],
            )
            if spec["role"] == "fast":
                sku_update = SkuUpdate(
                    retail_ex_vat=retail,
                    wholesale_ex_vat=wholesale,
                    category=spec["category"],
                    preferred_supplier_id=suppliers[spec["supplier_key"]],
                    lead_time_days=lead,
                    supplier_ref=spec["supplier_ref"],
                    reorder_min=6,
                )
            elif spec["role"] == "normal":
                sku_update = SkuUpdate(
                    retail_ex_vat=retail,
                    wholesale_ex_vat=wholesale,
                    category=spec["category"],
                    preferred_supplier_id=suppliers[spec["supplier_key"]],
                    lead_time_days=lead,
                    supplier_ref=spec["supplier_ref"],
                    reorder_min=3,
                )
            await self.seed._ensure_transaction()
            await sku_service.update(created.id, sku_update)
            if photo:
                await self.seed._ensure_transaction()
                await self.seed._attach_photo_if_needed(sku_service, created.id, photo)
            out[spec["our_ref"]] = created.id
        return out

    async def _seed_purchase_orders(
        self,
        owner_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        suppliers: dict[str, uuid.UUID],
        skus: dict[str, uuid.UUID],
    ) -> None:
        po_service = PurchaseOrderService(self.db)
        po_crud = PurchaseOrderCRUD(self.db)
        grouped: dict[tuple[str, int], list[tuple[str, int]]] = defaultdict(list)
        for spec in BI_SKUS:
            for qty, receive_ago in po_waves(spec["role"]):
                if qty <= 0:
                    continue
                grouped[(spec["supplier_key"], receive_ago)].append((spec["our_ref"], qty))

        po_index = 0
        for (supplier_key, receive_ago), lines_spec in grouped.items():
            supplier_id = suppliers[supplier_key]
            currency = next(s["default_currency"] for s in BI_SUPPLIERS if s["key"] == supplier_key)
            catalog = {row["our_ref"]: row for row in BI_SKUS}
            max_lead = 0
            po_lines: list[PoLineCreate] = []
            factory_total = Decimal("0.00")
            for our_ref, qty in lines_spec:
                spec = catalog[our_ref]
                max_lead = max(max_lead, lead_days_for(spec["supplier_key"], spec["category"]))
                retail = Decimal(spec["retail_ex"])
                _wholesale, unit_cost = pricing_for_role(retail, spec["role"])
                if currency == "ZAR":
                    factory_unit = unit_cost
                else:
                    factory_unit = (unit_cost / EUR_FX).quantize(CENT)
                    if factory_unit < Decimal("1.00"):
                        factory_unit = Decimal("1.00")
                po_lines.append(
                    PoLineCreate(
                        sku_id=skus[our_ref],
                        qty=qty,
                        factory_unit_amount=factory_unit,
                    )
                )
                factory_total += factory_unit * qty
            if not po_lines:
                continue
            po_index += 1
            freight = max(Decimal("800.00"), (factory_total * Decimal("0.08")).quantize(CENT))
            clearance = max(Decimal("300.00"), (factory_total * Decimal("0.03")).quantize(CENT))
            fx = Decimal("1.00") if currency == "ZAR" else EUR_FX
            await self.seed._ensure_transaction()
            po = await po_service.create(
                PurchaseOrderCreate(supplier_id=supplier_id, lines=po_lines)
            )
            await self.seed._ensure_transaction()
            await po_service.mark_on_water(po.id)
            await self.seed._ensure_transaction()
            await po_service.land(
                po_id=po.id,
                user_id=owner_id,
                fx_to_zar=fx,
                factory_invoice_number=f"BI-FAC-{po_index:03d}",
                factory_amount=factory_total,
                factory_currency=currency,
                factory_file=_pdf_upload(f"bi-factory-{po_index}.pdf"),
                freight_invoice_number=f"BI-FRT-{po_index:03d}",
                freight_amount=freight,
                freight_currency="ZAR",
                freight_file=_pdf_upload(f"bi-freight-{po_index}.pdf"),
                clearance_invoice_number=f"BI-CLR-{po_index:03d}",
                clearance_amount=clearance,
                clearance_currency="ZAR",
                clearance_file=_pdf_upload(f"bi-clearance-{po_index}.pdf"),
            )
            await self.seed._ensure_transaction()
            await po_service.receive(
                ReceiveRequest(purchase_order_id=po.id, location_id=warehouse_id),
                user_id=owner_id,
            )
            for our_ref, qty in lines_spec:
                self.warehouse[our_ref] += qty
                prev = self.first_received_ago.get(our_ref)
                if prev is None or receive_ago > prev:
                    self.first_received_ago[our_ref] = receive_ago

            received_at = _utc(receive_ago)
            ordered_at = received_at - datetime.timedelta(days=max_lead)
            on_water_at = ordered_at + datetime.timedelta(days=max(5, max_lead // 4))
            landed_at = received_at - datetime.timedelta(days=min(10, max(3, max_lead // 10)))
            if landed_at <= on_water_at:
                landed_at = on_water_at + datetime.timedelta(days=3)
            if landed_at >= received_at:
                landed_at = received_at - datetime.timedelta(days=2)
                on_water_at = min(on_water_at, landed_at - datetime.timedelta(days=2))
            await self.seed._ensure_transaction()
            async with unit_of_work(self.db):
                row = await po_crud.get_by_id(po.id)
                if row is not None:
                    row.ordered_at = ordered_at
                    row.on_water_at = on_water_at
                    row.landed_at = landed_at
                    row.received_at = received_at

    async def _seed_transfers(
        self,
        owner_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        showroom_id: uuid.UUID,
        skus: dict[str, uuid.UUID],
    ) -> None:
        transfer_service = TransferService(self.db)
        transfer_crud = TransferCRUD(self.db)
        by_receive: dict[int, list[tuple[uuid.UUID, int, str]]] = defaultdict(list)
        leftover: list[tuple[str, str]] = []
        overstock_show: list[str] = []
        for spec in BI_SKUS:
            po_qty, transfer_qty, _sell = qty_for_role(spec["role"])
            ref = spec["our_ref"]
            if transfer_qty > 0:
                if self.warehouse[ref] < transfer_qty:
                    raise RuntimeError(
                        f"BI pack: cannot transfer {transfer_qty} of {ref}, "
                        f"warehouse has {self.warehouse[ref]}"
                    )
                receive_ago = self.first_received_ago[ref]
                by_receive[receive_ago].append((skus[ref], transfer_qty, ref))
            leftover_qty = po_qty - transfer_qty
            if leftover_qty > 0:
                leftover.append((ref, spec["role"]))
            if spec["role"] == "overstock" and transfer_qty > 0:
                overstock_show.append(ref)

        # Transfer after the units have been received (days_ago < receive_ago).
        for receive_ago, items in sorted(by_receive.items(), reverse=True):
            transfer_ago = receive_ago - 12
            if transfer_ago < 4:
                transfer_ago = 3
            chunk = [(sku_id, qty) for sku_id, qty, _ref in items]
            transfer_id = await self._create_transfer(
                transfer_service,
                owner_id,
                warehouse_id,
                showroom_id,
                chunk,
                notes=f"{BI_PACK_NOTES_PREFIX} received K-to-B {receive_ago}d",
                dispatch=True,
                receive=True,
            )
            await self._stamp_transfer(
                transfer_crud, transfer_id, days_ago=transfer_ago, received=True
            )
            for sku_id, qty, ref in items:
                self.warehouse[ref] -= qty
                self.showroom[ref] += qty
                self.showroom_since_ago[ref] = transfer_ago

        in_transit_refs = [
            ref for ref, role in leftover if role != "dead" and self.warehouse[ref] >= 1
        ][:5]
        if in_transit_refs:
            t1 = await self._create_transfer(
                transfer_service,
                owner_id,
                warehouse_id,
                showroom_id,
                [(skus[ref], 1) for ref in in_transit_refs[:3]],
                notes=f"{BI_PACK_NOTES_PREFIX} in-transit K-to-B",
                dispatch=True,
                receive=False,
            )
            await self._stamp_transfer(transfer_crud, t1, days_ago=9, received=False)
            for ref in in_transit_refs[:3]:
                self.warehouse[ref] -= 1
        if len(in_transit_refs) > 3:
            t2 = await self._create_transfer(
                transfer_service,
                owner_id,
                warehouse_id,
                showroom_id,
                [(skus[ref], 1) for ref in in_transit_refs[3:]],
                notes=f"{BI_PACK_NOTES_PREFIX} in-transit K-to-B 2",
                dispatch=True,
                receive=False,
            )
            await self._stamp_transfer(transfer_crud, t2, days_ago=4, received=False)
            for ref in in_transit_refs[3:]:
                self.warehouse[ref] -= 1

        draft_refs = [
            ref for ref, role in leftover if role == "normal" and self.warehouse[ref] >= 1
        ][:3]
        if draft_refs:
            await self._create_transfer(
                transfer_service,
                owner_id,
                warehouse_id,
                showroom_id,
                [(skus[ref], 1) for ref in draft_refs],
                notes=f"{BI_PACK_NOTES_PREFIX} draft K-to-B",
                dispatch=False,
                receive=False,
            )

        reverse_refs = [ref for ref in overstock_show if self.showroom[ref] >= 1][:2]
        if reverse_refs:
            reverse_id = await self._create_transfer(
                transfer_service,
                owner_id,
                showroom_id,
                warehouse_id,
                [(skus[ref], 1) for ref in reverse_refs],
                notes=f"{BI_PACK_NOTES_PREFIX} received B-to-K",
                dispatch=True,
                receive=True,
            )
            await self._stamp_transfer(transfer_crud, reverse_id, days_ago=20, received=True)
            for ref in reverse_refs:
                self.showroom[ref] -= 1
                self.warehouse[ref] += 1

        draft_rev = [ref for ref in overstock_show[2:4] if self.showroom[ref] >= 1]
        if draft_rev:
            await self._create_transfer(
                transfer_service,
                owner_id,
                showroom_id,
                warehouse_id,
                [(skus[ref], 1) for ref in draft_rev],
                notes=f"{BI_PACK_NOTES_PREFIX} draft B-to-K",
                dispatch=False,
                receive=False,
            )

    async def _create_transfer(
        self,
        transfer_service: TransferService,
        owner_id: uuid.UUID,
        from_id: uuid.UUID,
        to_id: uuid.UUID,
        items: list[tuple[uuid.UUID, int]],
        *,
        notes: str,
        dispatch: bool,
        receive: bool,
    ) -> uuid.UUID:
        await self.seed._ensure_transaction()
        draft = await transfer_service.create(
            TransferCreate(
                from_location_id=from_id,
                to_location_id=to_id,
                notes=notes,
                lines=[TransferLineCreate(sku_id=sku_id, qty=qty) for sku_id, qty in items],
            ),
            owner_id,
        )
        if not dispatch:
            return draft.id
        await self.seed._ensure_transaction()
        dispatched = await transfer_service.dispatch(draft.id, owner_id)
        if not receive:
            return dispatched.id
        await self.seed._ensure_transaction()
        received = await transfer_service.receive(
            dispatched.id,
            TransferReceive(
                lines=[
                    TransferReceiveLine(line_id=line.id, qty_received=line.qty_dispatched)
                    for line in dispatched.lines
                ]
            ),
            owner_id,
        )
        return received.id

    async def _stamp_transfer(
        self,
        transfer_crud: TransferCRUD,
        transfer_id: uuid.UUID,
        *,
        days_ago: int,
        received: bool,
    ) -> None:
        created = _naive_utc(days_ago)
        await self.seed._ensure_transaction()
        async with unit_of_work(self.db):
            row = await transfer_crud.get_by_id(transfer_id)
            if row is None:
                return
            row.created_at = created
            if row.dispatched_at is not None:
                row.dispatched_at = created + datetime.timedelta(days=1)
            if received and row.received_at is not None:
                row.received_at = created + datetime.timedelta(days=3)

    async def _seed_till_sales(
        self,
        showroom_id: uuid.UUID,
        customers: dict[str, uuid.UUID],
        skus: dict[str, uuid.UUID],
        today: datetime.date,
    ) -> None:
        till = TillOrchestrator(self.db)
        retail_names = [spec["name"] for spec in BI_CUSTOMERS if spec["customer_type"] == "retail"]
        sell_units: list[str] = []
        for spec in BI_SKUS:
            _po, transfer_qty, sell_qty = qty_for_role(spec["role"])
            if spec["role"] not in ("fast", "cheap"):
                continue
            if sell_qty <= 0 or transfer_qty <= 0:
                continue
            ref = spec["our_ref"]
            if self.showroom[ref] < sell_qty:
                raise RuntimeError(
                    f"BI pack: cannot till-sell {sell_qty} of {ref}, "
                    f"showroom has {self.showroom[ref]}"
                )
            for _ in range(sell_qty):
                sell_units.append(ref)

        tickets: list[list[str]] = []
        for i in range(0, len(sell_units), 2):
            tickets.append(sell_units[i : i + 2])

        tenders = ["cash", "card"]
        for index, refs in enumerate(tickets):
            await self.seed._ensure_transaction()
            customer_id = None
            if index % 3 == 0 and retail_names:
                customer_id = customers[retail_names[index % len(retail_names)]]
            sale = await till.create_sale(
                TillSaleCreate(
                    location_id=showroom_id,
                    customer_id=customer_id,
                    lines=[TillSaleLineCreate(sku_id=skus[ref], qty=1) for ref in refs],
                    tender=tenders[index % 2],  # type: ignore[arg-type]
                )
            )
            for ref in refs:
                self.showroom[ref] -= 1
            # Sale date after the unit reached Bedfordview (never same-week as a long-lead receive).
            floor_ago = min(self.showroom_since_ago[ref] for ref in refs)
            sale_ago = max(4, floor_ago - 8 - index * 7)
            if sale_ago >= floor_ago:
                sale_ago = max(2, floor_ago - 3)
            sale_day = today - datetime.timedelta(days=sale_ago)
            await self._stamp_invoice_dates(sale.invoice_id, sale.payment_id, sale_day)

    async def _seed_invoices(
        self,
        customers: dict[str, uuid.UUID],
        today: datetime.date,
    ) -> None:
        # Books invoices do not move stock. Do not stamp sku_id — that would
        # report SKU sales of units still on hand. AR mix is still useful for Nia.
        invoice_service = InvoiceService(self.db)
        payment_service = PaymentService(self.db)
        trade_names = [spec["name"] for spec in BI_CUSTOMERS if spec["customer_type"] == "trade"]
        retail_names = [spec["name"] for spec in BI_CUSTOMERS if spec["customer_type"] == "retail"]
        plans = ["paid"] * 8 + ["partial"] * 8 + ["overdue"] * 8
        existing = await self._count_bi_invoices()
        for i, status in enumerate(plans):
            if i < existing:
                continue
            if status == "overdue":
                days = 45 + (i * 6)
                name = trade_names[i % len(trade_names)]
                desc = f"{BI_PACK_NOTES_PREFIX} trade seating specification"
                unit = Decimal("18500.00")
            elif status == "partial":
                days = 18 + (i * 8)
                name = trade_names[i % len(trade_names)]
                desc = f"{BI_PACK_NOTES_PREFIX} trade dining specification"
                unit = Decimal("9800.00")
            else:
                days = 10 + (i * 12)
                name = (
                    retail_names[i % len(retail_names)]
                    if i % 2 == 0
                    else trade_names[i % len(trade_names)]
                )
                desc = f"{BI_PACK_NOTES_PREFIX} design consultation / freight"
                unit = Decimal("2500.00")
            issue = today - datetime.timedelta(days=days)
            await self.seed._ensure_transaction()
            invoice = await invoice_service.create(
                InvoiceCreate(
                    customer_id=customers[name],
                    issue_date=issue,
                    lines=[
                        InvoiceLineCreate(
                            description=desc,
                            qty=1,
                            unit_ex_vat=unit,
                        )
                    ],
                )
            )
            if status == "paid":
                await self.seed._ensure_transaction()
                await payment_service.create(
                    PaymentCreate(
                        direction="in",
                        invoice_id=invoice.id,
                        amount=invoice.total_inc_vat,
                        currency="ZAR",
                        paid_on=issue + datetime.timedelta(days=5),
                    )
                )
            elif status == "partial":
                # PaymentService requires the remaining balance in full.
                # Stamp amount_paid so Nia still sees partial AR.
                await self._stamp_partial_balance(invoice.id)
        await self._backfill_partial_balances()

    async def _seed_laybys(
        self,
        owner_id: uuid.UUID,
        showroom_id: uuid.UUID,
        customers: dict[str, uuid.UUID],
        skus: dict[str, uuid.UUID],
        today: datetime.date,
    ) -> None:
        if await self._count_bi_laybys() > 0:
            return
        laybys = LaybysService(self.db)
        retail_names = [spec["name"] for spec in BI_CUSTOMERS if spec["customer_type"] == "retail"]
        candidates = [
            spec
            for spec in BI_SKUS
            if spec["role"] == "fast"
            and spec["category"] in ("Seating", "Dining", "Bedroom")
            and self.showroom[spec["our_ref"]] >= 1
        ][:6]
        plans = [
            ("open", True, Decimal("0.20")),
            ("open", True, Decimal("0.25")),
            ("partial", True, Decimal("0.30")),
            ("partial", False, Decimal("0.35")),
            ("completed", True, Decimal("1.00")),
            ("completed", True, Decimal("1.00")),
        ]
        for index, spec in enumerate(candidates):
            kind, hold, deposit_frac = plans[index]
            if hold and self.showroom[spec["our_ref"]] < 1:
                continue
            retail = Decimal(spec["retail_ex"])
            total_inc = ex_to_inc(retail)
            deposit = (total_inc * deposit_frac).quantize(CENT)
            if deposit <= 0:
                deposit = Decimal("500.00")
            if deposit >= total_inc and kind != "completed":
                deposit = (total_inc * Decimal("0.25")).quantize(CENT)
            if kind == "completed":
                deposit = total_inc
            due = today + datetime.timedelta(days=60 if kind == "open" else 30)
            if kind == "completed":
                due = today - datetime.timedelta(days=10)
            await self.seed._ensure_transaction()
            created = await laybys.create(
                LaybyCreate(
                    customer_id=customers[retail_names[index % len(retail_names)]],
                    location_id=showroom_id,
                    due_date=due,
                    hold_stock=hold,
                    deposit_amount=deposit,
                    tender="card" if index % 2 else "cash",
                    lines=[LaybyLineCreate(sku_id=skus[spec["our_ref"]], qty=1)],
                    notes=f"{BI_PACK_NOTES_PREFIX} layby {kind} {index + 1}",
                ),
                owner_id,
            )
            if hold:
                self.showroom[spec["our_ref"]] -= 1
            if kind == "partial":
                extra = (created.total_inc_vat * Decimal("0.25")).quantize(CENT)
                if extra > 0 and created.amount_paid + extra < created.total_inc_vat:
                    await self.seed._ensure_transaction()
                    await laybys.add_payment(
                        created.id,
                        LaybyPaymentCreate(amount=extra, tender="cash"),
                        owner_id,
                    )
            if kind == "completed":
                await self.seed._ensure_transaction()
                completed = await laybys.complete(created.id, owner_id)
                floor_ago = self.showroom_since_ago.get(spec["our_ref"], 20)
                complete_ago = max(4, min(12 + index, floor_ago - 3))
                if completed.invoice_id is not None:
                    await self._stamp_invoice_dates(
                        completed.invoice_id,
                        None,
                        today - datetime.timedelta(days=complete_ago),
                    )

    async def _seed_bills(
        self,
        suppliers: dict[str, uuid.UUID],
        today: datetime.date,
    ) -> None:
        bill_service = BillService(self.db)
        payment_service = PaymentService(self.db)
        rows = [
            ("ethnicraft", "BI-BILL-ETH-01", Decimal("18500.00"), 80, True),
            ("kramlight", "BI-BILL-KL-01", Decimal("6400.00"), 40, True),
            ("patio", "BI-BILL-PL-01", Decimal("22300.00"), 55, False),
            ("weylandts", "BI-BILL-WY-01", Decimal("9800.00"), 25, True),
        ]
        existing_refs = {bill.supplier_ref for bill in await BillCRUD(self.db).list_all()}
        for key, ref, amount, days_ago, paid in rows:
            if ref in existing_refs:
                continue
            issue = today - datetime.timedelta(days=days_ago)
            await self.seed._ensure_transaction()
            bill = await bill_service.create(
                BillCreate(
                    supplier_id=suppliers[key],
                    supplier_ref=ref,
                    issue_date=issue,
                    currency="ZAR",
                    fx_to_zar=Decimal("1.00"),
                    lines=[
                        BillLineCreate(
                            description=f"{BI_PACK_NOTES_PREFIX} {ref}",
                            qty=1,
                            unit_amount=amount,
                        )
                    ],
                )
            )
            if paid:
                await self.seed._ensure_transaction()
                await payment_service.create(
                    PaymentCreate(
                        direction="out",
                        bill_id=bill.id,
                        amount=bill.amount_foreign,
                        currency="ZAR",
                        fx_to_zar=Decimal("1.00"),
                        paid_on=issue + datetime.timedelta(days=10),
                    )
                )

    async def _age_dead_stock(
        self,
        warehouse_id: uuid.UUID,
        skus: dict[str, uuid.UUID],
    ) -> None:
        dead_ids = [skus[spec["our_ref"]] for spec in BI_SKUS if spec["role"] == "dead"]
        if not dead_ids:
            return
        aged = _naive_utc(220)
        await self.seed._ensure_transaction()
        async with unit_of_work(self.db):
            await self.db.execute(
                update(LocationStock)
                .where(
                    LocationStock.sku_id.in_(dead_ids),
                    LocationStock.location_id == warehouse_id,
                )
                .values(updated_at=aged)
                .execution_options(synchronize_session=False)
            )

    async def _stamp_invoice_dates(
        self,
        invoice_id: uuid.UUID,
        payment_id: Optional[uuid.UUID],
        when: datetime.date,
    ) -> None:
        await self.seed._ensure_transaction()
        async with unit_of_work(self.db):
            invoice = await self.db.get(TaxInvoice, invoice_id)
            if invoice is not None:
                invoice.issue_date = when
            if payment_id is not None:
                payment = await self.db.get(Payment, payment_id)
                if payment is not None:
                    payment.paid_on = when

    def _resolve_photo(self, preferred: str) -> Optional[str]:
        from app.services.playground_seed import PLAYGROUND_PHOTOS_DIR

        preferred_path = PLAYGROUND_PHOTOS_DIR / preferred
        if preferred_path.is_file():
            return preferred
        for path in sorted(PLAYGROUND_PHOTOS_DIR.glob("*.jpg")):
            return path.name
        return None


async def seed_bi_pack(seed: PlaygroundSeedService) -> None:
    await PlaygroundBiPack(seed).seed_if_needed()
