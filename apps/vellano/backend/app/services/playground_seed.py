from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from typing import Optional

from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.crud.bill import BillCRUD
from app.crud.location import LocationCRUD
from app.crud.sku import SkuCRUD
from app.crud.supplier import SupplierCRUD
from app.crud.user import UserCRUD
from app.models.customer import Customer
from app.models.layby import Layby
from app.models.tax_invoice import InvoiceLine
from app.schemas.bank_import import BankImportMatchRequest
from app.schemas.bill import BillCreate, BillLineCreate
from app.schemas.contact import ContactCreate
from app.schemas.customer_crm import CustomerCrmCreate
from app.schemas.invoice import InvoiceCreate, InvoiceLineCreate
from app.schemas.layby import LaybyCreate, LaybyLineCreate
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
from app.services.bank_imports import BankImportService
from app.services.bills import BillService
from app.services.contacts import ContactService
from app.services.customers_crm import CustomersCrmService
from app.services.invoices import InvoiceService
from app.services.laybys import LaybysService
from app.services.locations import LocationSeedService
from app.services.payments import PaymentService
from app.services.proformas import ProformaService
from app.services.purchase_orders import PurchaseOrderService
from app.services.skus import SkuService
from app.services.suppliers import SupplierService
from app.services.till_orchestrator import TillOrchestrator
from app.services.transfers import TransferService
from app.services.vat import ex_to_inc
from f0rge_core.exceptions import NotFoundError

MINIMAL_PDF = b"%PDF-1.1\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"

PLAYGROUND_SUPPLIER_NAME = "Playground Imports"
MARKER_SKU_REF = "PG-TABLE"
CHAIR_SKU_REF = "PG-CHAIR"
PACK_MARKER_REF = "PG-SOFA"
SOFA_PACK_MARKER_REF = "VEL-SOFA-LONDON"
MINOTTI_SUPPLIER_NAME = "Minotti Agency JHB"
VEL_BILL_SUPPLIER_REF = "VEL-MINOTTI-001"
VEL_TRADE_INVOICE_LINE = "Milano L-shape natural linen — trade specification"
VEL_LAYBY_NOTES = "VEL catalogue London sofa layby"
PROFORMA_INVOICE_NUMBER = "PF-PLAY-001"
PLAYGROUND_CUSTOMER_NAME = "Playground Customer"
FX_BILL_SUPPLIER_REF = "PG-FX-001"

PLAYGROUND_PHOTOS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "playground_photos"


def _pdf_upload(filename: str) -> UploadFile:
    return UploadFile(file=BytesIO(MINIMAL_PDF), filename=filename)


class PlaygroundSeedService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.supplier_crud = SupplierCRUD(db)
        self.sku_crud = SkuCRUD(db)
        self.location_crud = LocationCRUD(db)
        self.user_crud = UserCRUD(db)

    async def seed_if_enabled(self) -> None:
        if not settings.seed_playground:
            return
        if not await self._already_seeded():
            await self._seed()
        await self._seed_demo_pack()
        await self._seed_sofa_catalog_pack()

    async def _already_seeded(self) -> bool:
        if await self.supplier_crud.get_by_name_insensitive(PLAYGROUND_SUPPLIER_NAME) is not None:
            return True
        if await self.sku_crud.get_by_our_ref(MARKER_SKU_REF) is not None:
            return True
        return False

    async def _seed(self) -> None:
        owner = await self.user_crud.get_by_email(settings.seed_owner_email)
        if owner is None:
            raise NotFoundError("Owner user not found for playground seed")

        today = datetime.date.today()
        await self._ensure_transaction()
        supplier_service = SupplierService(self.db)
        sku_service = SkuService(self.db)
        proforma_service = ProformaService(self.db)
        po_service = PurchaseOrderService(self.db)
        transfer_service = TransferService(self.db)
        contact_service = ContactService(self.db)
        invoice_service = InvoiceService(self.db)
        till_orchestrator = TillOrchestrator(self.db)
        bill_service = BillService(self.db)
        payment_service = PaymentService(self.db)
        bank_import_service = BankImportService(self.db)

        supplier = await supplier_service.create(
            SupplierCreate(name=PLAYGROUND_SUPPLIER_NAME, default_currency="ZAR")
        )

        table_sku = await sku_service.create(
            SkuCreate(
                our_ref=MARKER_SKU_REF,
                our_barcode="PG-TABLE-1",
                name="Playground dining table",
                design="Playground table design",
                fabric="Playground oak",
            ),
            owner.id,
        )
        await sku_service.update(
            table_sku.id,
            SkuUpdate(retail_ex_vat=Decimal("10000.00"), wholesale_ex_vat=Decimal("7000.00")),
        )

        chair_sku = await sku_service.create(
            SkuCreate(
                our_ref=CHAIR_SKU_REF,
                our_barcode="PG-CHAIR-1",
                name="Playground dining chair",
                design="Playground chair design",
                fabric="Playground fabric",
            ),
            owner.id,
        )
        await sku_service.update(
            chair_sku.id,
            SkuUpdate(retail_ex_vat=Decimal("2000.00"), wholesale_ex_vat=Decimal("1400.00")),
        )

        proforma = await proforma_service.create(
            supplier_id=supplier.id,
            invoice_number=PROFORMA_INVOICE_NUMBER,
            invoice_date=today,
            currency="ZAR",
            file=_pdf_upload("playground-proforma.pdf"),
        )

        po = await po_service.create(
            PurchaseOrderCreate(
                supplier_id=supplier.id,
                proforma_id=proforma.id,
                lines=[
                    PoLineCreate(
                        sku_id=table_sku.id,
                        qty=2,
                        factory_unit_amount=Decimal("400.00"),
                    ),
                    PoLineCreate(
                        sku_id=chair_sku.id,
                        qty=2,
                        factory_unit_amount=Decimal("80.00"),
                    ),
                ],
            )
        )

        await po_service.mark_on_water(po.id)

        await po_service.land(
            po_id=po.id,
            user_id=owner.id,
            fx_to_zar=Decimal("1.00"),
            factory_invoice_number="PG-FACTORY-001",
            factory_amount=Decimal("960.00"),
            factory_currency="ZAR",
            factory_file=_pdf_upload("factory.pdf"),
            freight_invoice_number="PG-FREIGHT-001",
            freight_amount=Decimal("200.00"),
            freight_currency="ZAR",
            freight_file=_pdf_upload("freight.pdf"),
            clearance_invoice_number="PG-CLEARANCE-001",
            clearance_amount=Decimal("100.00"),
            clearance_currency="ZAR",
            clearance_file=_pdf_upload("clearance.pdf"),
        )

        kramerville = await self._location_by_name(LocationSeedService.SEED_ROWS[0][0])
        bedfordview = await self._location_by_name(LocationSeedService.SEED_ROWS[1][0])

        await po_service.receive(
            ReceiveRequest(purchase_order_id=po.id, location_id=kramerville.id),
            user_id=owner.id,
        )

        await self._ensure_transaction()
        draft = await transfer_service.create(
            TransferCreate(
                from_location_id=kramerville.id,
                to_location_id=bedfordview.id,
                lines=[TransferLineCreate(sku_id=table_sku.id, qty=1)],
            ),
            owner.id,
        )
        await self._ensure_transaction()
        dispatched = await transfer_service.dispatch(draft.id, owner.id)
        await self._ensure_transaction()
        await transfer_service.receive(
            dispatched.id,
            TransferReceive(
                lines=[
                    TransferReceiveLine(
                        line_id=line.id,
                        qty_received=line.qty_dispatched,
                    )
                    for line in dispatched.lines
                ]
            ),
            owner.id,
        )

        # Services that nest commit_refresh inside unit_of_work need an
        # already-open transaction. A prior unit_of_work commit leaves none.
        await self._ensure_transaction()
        customer = await contact_service.create_customer(
            ContactCreate(name=PLAYGROUND_CUSTOMER_NAME)
        )
        await self._ensure_transaction()
        invoice = await invoice_service.create(
            InvoiceCreate(
                customer_id=customer.id,
                issue_date=today,
                lines=[
                    InvoiceLineCreate(
                        description="Playground dining chair",
                        qty=1,
                        unit_ex_vat=Decimal("2000.00"),
                    )
                ],
            )
        )

        await self._ensure_transaction()
        invoice_payment = await payment_service.create(
            PaymentCreate(
                direction="in",
                invoice_id=invoice.id,
                amount=invoice.total_inc_vat,
                currency="ZAR",
                paid_on=today,
            )
        )

        await self._ensure_transaction()
        await till_orchestrator.create_sale(
            TillSaleCreate(
                location_id=bedfordview.id,
                lines=[TillSaleLineCreate(sku_id=table_sku.id, qty=1)],
                tender="cash",
            )
        )

        await self._ensure_transaction()
        fx_bill = await bill_service.create(
            BillCreate(
                supplier_id=supplier.id,
                supplier_ref=FX_BILL_SUPPLIER_REF,
                issue_date=today,
                currency="USD",
                fx_to_zar=Decimal("18.50"),
                lines=[
                    BillLineCreate(
                        description="Playground FX freight",
                        qty=1,
                        unit_amount=Decimal("100.00"),
                    )
                ],
            )
        )

        await self._ensure_transaction()
        bill_payment = await payment_service.create(
            PaymentCreate(
                direction="out",
                bill_id=fx_bill.id,
                amount=fx_bill.amount_foreign,
                currency="USD",
                fx_to_zar=Decimal("18.50"),
                paid_on=today,
            )
        )

        await self._ensure_transaction()
        csv_content = (
            "Date,Description,Reference,Amount\n"
            f"{today.isoformat()},Customer payment playground,REF-PG-INV,{invoice_payment.amount_zar}\n"
            f"{today.isoformat()},Supplier payment playground,REF-PG-BILL,-{bill_payment.amount_zar}\n"
            f"{today.isoformat()},Unmatched deposit,REF-PG-UNMATCHED,500.00\n"
        ).encode()
        bank_import = await bank_import_service.create_from_csv("playground-bank.csv", csv_content)

        invoice_line = next(
            line for line in bank_import.lines if line.amount_zar == invoice_payment.amount_zar
        )
        bill_line = next(
            line for line in bank_import.lines if line.amount_zar == -bill_payment.amount_zar
        )
        await self._ensure_transaction()
        await bank_import_service.match_line(
            bank_import.id,
            invoice_line.id,
            BankImportMatchRequest(payment_id=invoice_payment.id),
        )
        await bank_import_service.match_line(
            bank_import.id,
            bill_line.id,
            BankImportMatchRequest(payment_id=bill_payment.id),
        )

    async def _seed_demo_pack(self) -> None:
        if await self.sku_crud.get_by_our_ref(PACK_MARKER_REF) is not None:
            return

        owner = await self.user_crud.get_by_email(settings.seed_owner_email)
        if owner is None:
            raise NotFoundError("Owner user not found for playground seed")

        kramerville = await self._location_by_name(LocationSeedService.SEED_ROWS[0][0])
        bedfordview = await self._location_by_name(LocationSeedService.SEED_ROWS[1][0])
        today = datetime.date.today()

        await self._ensure_transaction()
        sku_service = SkuService(self.db)
        crm = CustomersCrmService(self.db)
        laybys = LaybysService(self.db)
        invoice_service = InvoiceService(self.db)

        table = await self.sku_crud.get_by_our_ref(MARKER_SKU_REF)
        if table is not None:
            await sku_service.update(table.id, SkuUpdate(category="Tables"))
        chair = await self.sku_crud.get_by_our_ref(CHAIR_SKU_REF)
        if chair is not None:
            await sku_service.update(chair.id, SkuUpdate(category="Seating"))

        sofa = await self._create_opening_sku(
            sku_service,
            owner.id,
            our_ref=PACK_MARKER_REF,
            our_barcode="PG-SOFA-1",
            name="Playground 3-seater sofa",
            design="Playground sofa design",
            fabric="Playground linen",
            category="Seating",
            retail_ex=Decimal("8000.00"),
            wholesale_ex=Decimal("5600.00"),
            location_id=bedfordview.id,
            qty=6,
            unit_cost=Decimal("3200.00"),
        )
        armchair = await self._create_opening_sku(
            sku_service,
            owner.id,
            our_ref="PG-ARMCHAIR",
            our_barcode="PG-ARM-1",
            name="Playground armchair",
            design="Playground armchair design",
            fabric="Playground velvet",
            category="Seating",
            retail_ex=Decimal("3500.00"),
            wholesale_ex=Decimal("2450.00"),
            location_id=bedfordview.id,
            qty=4,
            unit_cost=Decimal("1400.00"),
        )
        await self._create_opening_sku(
            sku_service,
            owner.id,
            our_ref="PG-COFFEE",
            our_barcode="PG-COFFEE-1",
            name="Playground coffee table",
            design="Playground coffee design",
            fabric="Playground oak",
            category="Tables",
            retail_ex=Decimal("2800.00"),
            wholesale_ex=Decimal("1960.00"),
            location_id=kramerville.id,
            qty=5,
            unit_cost=Decimal("900.00"),
        )
        await self._create_opening_sku(
            sku_service,
            owner.id,
            our_ref="PG-SIDEBOARD",
            our_barcode="PG-SIDE-1",
            name="Playground sideboard",
            design="Playground sideboard design",
            fabric="Playground mango",
            category="Storage",
            retail_ex=Decimal("4200.00"),
            wholesale_ex=Decimal("2940.00"),
            location_id=bedfordview.id,
            qty=3,
            unit_cost=Decimal("1680.00"),
        )
        await self._create_opening_sku(
            sku_service,
            owner.id,
            our_ref="PG-LAMP",
            our_barcode="PG-LAMP-1",
            name="Playground floor lamp",
            design="Playground lamp design",
            fabric="Playground brass",
            category="Decor",
            retail_ex=Decimal("1100.00"),
            wholesale_ex=Decimal("770.00"),
            location_id=bedfordview.id,
            qty=8,
            unit_cost=Decimal("380.00"),
        )
        await self._create_opening_sku(
            sku_service,
            owner.id,
            our_ref="PG-BOOKCASE",
            our_barcode="PG-BOOK-1",
            name="Playground bookcase",
            design="Playground bookcase design",
            fabric="Playground oak",
            category="Storage",
            retail_ex=Decimal("3100.00"),
            wholesale_ex=Decimal("2170.00"),
            location_id=kramerville.id,
            qty=4,
            unit_cost=Decimal("1050.00"),
        )
        ottoman = await self._create_opening_sku(
            sku_service,
            owner.id,
            our_ref="PG-OTTOMAN",
            our_barcode="PG-OTT-1",
            name="Playground ottoman",
            design="Playground ottoman design",
            fabric="Playground linen",
            category="Seating",
            retail_ex=Decimal("900.00"),
            wholesale_ex=Decimal("630.00"),
            location_id=bedfordview.id,
            qty=7,
            unit_cost=Decimal("280.00"),
        )

        await self._ensure_transaction()
        naledi = await crm.create(
            CustomerCrmCreate(
                name="Naledi Mokoena",
                email="naledi@example.com",
                phone="0820001001",
                customer_type="retail",
                price_tier="standard",
            )
        )
        await self._ensure_transaction()
        pieter = await crm.create(
            CustomerCrmCreate(
                name="Pieter van Wyk",
                email="pieter@example.com",
                phone="0820001002",
                customer_type="retail",
                price_tier="standard",
            )
        )
        await self._ensure_transaction()
        studio = await crm.create(
            CustomerCrmCreate(
                name="Studio K Interiors",
                email="accounts@studiok.example.com",
                phone="0110001003",
                customer_type="trade",
                price_tier="trade",
                vat_number="4123456789",
            )
        )
        await self._ensure_transaction()
        thandi = await crm.create(
            CustomerCrmCreate(
                name="Thandi Dlamini",
                email="thandi@example.com",
                phone="0820001004",
                customer_type="retail",
                price_tier="standard",
            )
        )

        ottoman_total = ex_to_inc(Decimal("900.00"))

        await self._ensure_transaction()
        await laybys.create(
            LaybyCreate(
                customer_id=naledi.id,
                location_id=bedfordview.id,
                due_date=today + datetime.timedelta(days=90),
                hold_stock=True,
                deposit_amount=Decimal("2000.00"),
                tender="cash",
                lines=[LaybyLineCreate(sku_id=sofa.id, qty=1)],
                notes="Playground open sofa layby",
            ),
            owner.id,
        )
        await self._ensure_transaction()
        await laybys.create(
            LaybyCreate(
                customer_id=pieter.id,
                location_id=bedfordview.id,
                due_date=today - datetime.timedelta(days=14),
                hold_stock=True,
                deposit_amount=Decimal("1000.00"),
                tender="card",
                lines=[LaybyLineCreate(sku_id=armchair.id, qty=1)],
                notes="Playground overdue armchair layby",
            ),
            owner.id,
        )
        await self._ensure_transaction()
        await laybys.create(
            LaybyCreate(
                customer_id=studio.id,
                location_id=bedfordview.id,
                due_date=today + datetime.timedelta(days=21),
                hold_stock=True,
                deposit_amount=ottoman_total,
                tender="cash",
                lines=[LaybyLineCreate(sku_id=ottoman.id, qty=1)],
                notes="Playground ready ottoman layby",
            ),
            owner.id,
        )
        await self._ensure_transaction()
        await laybys.create(
            LaybyCreate(
                customer_id=thandi.id,
                location_id=bedfordview.id,
                due_date=today + datetime.timedelta(days=60),
                hold_stock=False,
                deposit_amount=Decimal("1500.00"),
                tender="card",
                lines=[LaybyLineCreate(sku_id=sofa.id, qty=1)],
                notes="Playground unheld sofa layby",
            ),
            owner.id,
        )

        await self._ensure_transaction()
        await invoice_service.create(
            InvoiceCreate(
                customer_id=studio.id,
                issue_date=today,
                lines=[
                    InvoiceLineCreate(
                        description="Playground trade seating",
                        qty=2,
                        unit_ex_vat=Decimal("2450.00"),
                    )
                ],
            )
        )
        await self._ensure_transaction()
        await invoice_service.create(
            InvoiceCreate(
                customer_id=naledi.id,
                issue_date=today - datetime.timedelta(days=40),
                lines=[
                    InvoiceLineCreate(
                        description="Playground open balance",
                        qty=1,
                        unit_ex_vat=Decimal("1800.00"),
                    )
                ],
            )
        )

    async def _seed_sofa_catalog_pack(self) -> None:
        if await self.sku_crud.get_by_our_ref(SOFA_PACK_MARKER_REF) is not None:
            return

        owner = await self.user_crud.get_by_email(settings.seed_owner_email)
        if owner is None:
            raise NotFoundError("Owner user not found for playground seed")

        kramerville = await self._location_by_name(LocationSeedService.SEED_ROWS[0][0])
        bedfordview = await self._location_by_name(LocationSeedService.SEED_ROWS[1][0])
        today = datetime.date.today()

        await self._ensure_transaction()
        sku_service = SkuService(self.db)
        supplier_service = SupplierService(self.db)
        crm = CustomersCrmService(self.db)
        laybys = LaybysService(self.db)
        invoice_service = InvoiceService(self.db)
        bill_service = BillService(self.db)

        catalogue_rows = [
            {
                "our_ref": "VEL-SOFA-LONDON",
                "our_barcode": "VEL-LONDON-1",
                "name": "London 3-seater",
                "design": "London",
                "fabric": "Belgian linen sage",
                "category": "Seating",
                "photo": "london-3s.jpg",
                "location_id": bedfordview.id,
                "qty": 2,
                "retail_ex": Decimal("68500.00"),
            },
            {
                "our_ref": "VEL-SOFA-CHESTER",
                "our_barcode": "VEL-CHESTER-1",
                "name": "Chesterfield 3-seater",
                "design": "Chesterfield",
                "fabric": "Aniline leather tobacco",
                "category": "Seating",
                "photo": "chesterfield.jpg",
                "location_id": bedfordview.id,
                "qty": 1,
                "retail_ex": Decimal("89500.00"),
            },
            {
                "our_ref": "VEL-SOFA-BOUCLE",
                "our_barcode": "VEL-BOUCLE-1",
                "name": "Como 2-seater",
                "design": "Como",
                "fabric": "Ivory bouclé",
                "category": "Seating",
                "photo": "boucle-2s.jpg",
                "location_id": bedfordview.id,
                "qty": 2,
                "retail_ex": Decimal("54900.00"),
            },
            {
                "our_ref": "VEL-SOFA-LSHAPE",
                "our_barcode": "VEL-LSHAPE-1",
                "name": "Milano L-shape",
                "design": "Milano",
                "fabric": "Natural linen",
                "category": "Seating",
                "photo": "linen-lshape.jpg",
                "location_id": kramerville.id,
                "qty": 1,
                "retail_ex": Decimal("78500.00"),
            },
            {
                "our_ref": "VEL-SOFA-CHAISE",
                "our_barcode": "VEL-CHAISE-1",
                "name": "Capri chaise",
                "design": "Capri",
                "fabric": "Moss velvet",
                "category": "Seating",
                "photo": "velvet-chaise.jpg",
                "location_id": bedfordview.id,
                "qty": 1,
                "retail_ex": Decimal("47900.00"),
            },
            {
                "our_ref": "VEL-SOFA-CLOUD",
                "our_barcode": "VEL-CLOUD-1",
                "name": "Cloud modular 4-seat",
                "design": "Cloud modular",
                "fabric": "Performance cream",
                "category": "Seating",
                "photo": "modular-cloud.jpg",
                "location_id": bedfordview.id,
                "qty": 1,
                "retail_ex": Decimal("72500.00"),
            },
            {
                "our_ref": "VEL-SOFA-WALNUT",
                "our_barcode": "VEL-WALNUT-1",
                "name": "Kinfolk lounge",
                "design": "Kinfolk",
                "fabric": "Walnut taupe weave",
                "category": "Seating",
                "photo": "walnut-lounge.jpg",
                "location_id": bedfordview.id,
                "qty": 1,
                "retail_ex": Decimal("64900.00"),
            },
            {
                "our_ref": "VEL-SOFA-CURVE",
                "our_barcode": "VEL-CURVE-1",
                "name": "Arc curved sofa",
                "design": "Arc",
                "fabric": "Ivory bouclé curve",
                "category": "Seating",
                "photo": "ivory-curve.jpg",
                "location_id": bedfordview.id,
                "qty": 1,
                "retail_ex": Decimal("58900.00"),
            },
            {
                "our_ref": "VEL-SOFA-CHARCOAL",
                "our_barcode": "VEL-CHARCOAL-1",
                "name": "Deep-seat 3-seater",
                "design": "Deep-seat",
                "fabric": "Charcoal linen",
                "category": "Seating",
                "photo": "charcoal-deep.jpg",
                "location_id": kramerville.id,
                "qty": 2,
                "retail_ex": Decimal("62900.00"),
            },
            {
                "our_ref": "VEL-SOFA-SAND",
                "our_barcode": "VEL-SAND-1",
                "name": "Sand modular corner",
                "design": "Sand modular",
                "fabric": "Sand linen",
                "category": "Seating",
                "photo": "sand-modular.jpg",
                "location_id": bedfordview.id,
                "qty": 1,
                "retail_ex": Decimal("81900.00"),
            },
            {
                "our_ref": "VEL-SOFA-TEAK",
                "our_barcode": "VEL-TEAK-1",
                "name": "Palma outdoor sofa",
                "design": "Palma",
                "fabric": "Teak olefin",
                "category": "Outdoor",
                "photo": "outdoor-teak.jpg",
                "location_id": bedfordview.id,
                "qty": 1,
                "retail_ex": Decimal("55900.00"),
            },
            {
                "our_ref": "VEL-CHAIR-CLUB",
                "our_barcode": "VEL-CLUB-1",
                "name": "Club armchair",
                "design": "Club",
                "fabric": "Tobacco leather",
                "category": "Seating",
                "photo": "club-chair.jpg",
                "location_id": bedfordview.id,
                "qty": 3,
                "retail_ex": Decimal("28900.00"),
            },
            {
                "our_ref": "VEL-TABLE-MARBLE",
                "our_barcode": "VEL-MARBLE-1",
                "name": "Carrara marble coffee table",
                "design": "Carrara",
                "fabric": "White marble",
                "category": "Tables",
                "photo": "marble-coffee.jpg",
                "location_id": bedfordview.id,
                "qty": 2,
                "retail_ex": Decimal("18900.00"),
            },
        ]

        london_sku = None
        for row in catalogue_rows:
            wholesale_ex, unit_cost = self._vel_pricing(row["retail_ex"])
            sku = await self._create_opening_sku(
                sku_service,
                owner.id,
                our_ref=row["our_ref"],
                our_barcode=row["our_barcode"],
                name=row["name"],
                design=row["design"],
                fabric=row["fabric"],
                category=row["category"],
                retail_ex=row["retail_ex"],
                wholesale_ex=wholesale_ex,
                location_id=row["location_id"],
                qty=row["qty"],
                unit_cost=unit_cost,
                photo_filename=row["photo"],
            )
            if row["our_ref"] == SOFA_PACK_MARKER_REF:
                london_sku = sku

        minotti = await self.supplier_crud.get_by_name_insensitive(MINOTTI_SUPPLIER_NAME)
        if minotti is None:
            await self._ensure_transaction()
            minotti = await supplier_service.create(
                SupplierCreate(name=MINOTTI_SUPPLIER_NAME, default_currency="EUR")
            )

        hyde_park = await self._customer_by_name_insensitive("Hyde Park Living")
        if hyde_park is None:
            await self._ensure_transaction()
            hyde_park_resp = await crm.create(
                CustomerCrmCreate(
                    name="Hyde Park Living",
                    email="studio@hydeparkliving.example.com",
                    phone="0110002001",
                    customer_type="retail",
                    price_tier="standard",
                )
            )
            hyde_park = await self._customer_by_name_insensitive(hyde_park_resp.name)
        assert hyde_park is not None

        sandton_trade = await self._customer_by_name_insensitive("Atelier Sandton Interiors")
        if sandton_trade is None:
            await self._ensure_transaction()
            sandton_resp = await crm.create(
                CustomerCrmCreate(
                    name="Atelier Sandton Interiors",
                    email="accounts@ateliersandton.example.com",
                    phone="0110002002",
                    customer_type="trade",
                    price_tier="trade",
                    vat_number="4987654321",
                )
            )
            sandton_trade = await self._customer_by_name_insensitive(sandton_resp.name)
        assert sandton_trade is not None

        camps_bay = await self._customer_by_name_insensitive("Camps Bay Home")
        if camps_bay is None:
            await self._ensure_transaction()
            camps_resp = await crm.create(
                CustomerCrmCreate(
                    name="Camps Bay Home",
                    email="hello@campsbayhome.example.com",
                    phone="0210002003",
                    customer_type="retail",
                    price_tier="standard",
                )
            )
            camps_bay = await self._customer_by_name_insensitive(camps_resp.name)
        assert camps_bay is not None

        if not await self._invoice_line_exists(VEL_TRADE_INVOICE_LINE):
            await self._ensure_transaction()
            await invoice_service.create(
                InvoiceCreate(
                    customer_id=sandton_trade.id,
                    issue_date=today,
                    lines=[
                        InvoiceLineCreate(
                            description=VEL_TRADE_INVOICE_LINE,
                            qty=1,
                            unit_ex_vat=Decimal("54950.00"),
                        )
                    ],
                )
            )

        if london_sku is not None and not await self._layby_with_notes_exists(VEL_LAYBY_NOTES):
            await self._ensure_transaction()
            await laybys.create(
                LaybyCreate(
                    customer_id=hyde_park.id,
                    location_id=bedfordview.id,
                    due_date=today + datetime.timedelta(days=120),
                    hold_stock=True,
                    deposit_amount=Decimal("15000.00"),
                    tender="card",
                    lines=[LaybyLineCreate(sku_id=london_sku.id, qty=1)],
                    notes=VEL_LAYBY_NOTES,
                ),
                owner.id,
            )

        if not await self._bill_by_supplier_ref_exists(VEL_BILL_SUPPLIER_REF):
            await self._ensure_transaction()
            await bill_service.create(
                BillCreate(
                    supplier_id=minotti.id,
                    supplier_ref=VEL_BILL_SUPPLIER_REF,
                    issue_date=today,
                    currency="ZAR",
                    fx_to_zar=Decimal("1.00"),
                    lines=[
                        BillLineCreate(
                            description="Minotti container freight JHB",
                            qty=1,
                            unit_amount=Decimal("18500.00"),
                        )
                    ],
                )
            )

        _ = camps_bay

    @staticmethod
    def _vel_pricing(retail_ex: Decimal) -> tuple[Decimal, Decimal]:
        wholesale = (retail_ex * Decimal("0.70")).quantize(Decimal("0.01"))
        unit_cost = (retail_ex * Decimal("0.40")).quantize(Decimal("0.01"))
        return wholesale, unit_cost

    async def _create_opening_sku(
        self,
        sku_service: SkuService,
        owner_id: uuid.UUID,
        *,
        our_ref: str,
        our_barcode: str,
        name: str,
        design: str,
        fabric: str,
        category: str,
        retail_ex: Decimal,
        wholesale_ex: Decimal,
        location_id: uuid.UUID,
        qty: int,
        unit_cost: Decimal,
        photo_filename: Optional[str] = None,
    ):
        sku = await sku_service.create(
            SkuCreate(
                our_ref=our_ref,
                our_barcode=our_barcode,
                name=name,
                design=design,
                fabric=fabric,
                category=category,
                opening_location_id=location_id,
                opening_qty=qty,
                opening_unit_cost_zar=unit_cost,
            ),
            owner_id,
        )
        await sku_service.update(
            sku.id,
            SkuUpdate(
                retail_ex_vat=retail_ex,
                wholesale_ex_vat=wholesale_ex,
                category=category,
            ),
        )
        if photo_filename:
            await self._attach_photo_if_needed(sku_service, sku.id, photo_filename)
        reloaded = await self.sku_crud.get_by_id(sku.id)
        assert reloaded is not None
        return reloaded

    async def _attach_photo_if_needed(
        self,
        sku_service: SkuService,
        sku_id: uuid.UUID,
        photo_filename: str,
    ) -> None:
        sku = await self.sku_crud.get_by_id(sku_id)
        if sku is None or sku.photo_storage_key:
            return
        photo_path = PLAYGROUND_PHOTOS_DIR / photo_filename
        raw = photo_path.read_bytes()
        await sku_service.upload_photo(
            sku_id,
            UploadFile(file=BytesIO(raw), filename=photo_filename),
        )

    async def _customer_by_name_insensitive(self, name: str) -> Optional[Customer]:
        return (
            await self.db.execute(select(Customer).where(func.lower(Customer.name) == name.lower()))
        ).scalar_one_or_none()

    async def _invoice_line_exists(self, description: str) -> bool:
        row = (
            await self.db.execute(
                select(InvoiceLine.id).where(InvoiceLine.description == description).limit(1)
            )
        ).scalar_one_or_none()
        return row is not None

    async def _layby_with_notes_exists(self, notes: str) -> bool:
        row = (
            await self.db.execute(select(Layby.id).where(Layby.notes == notes).limit(1))
        ).scalar_one_or_none()
        return row is not None

    async def _bill_by_supplier_ref_exists(self, supplier_ref: str) -> bool:
        bill_crud = BillCRUD(self.db)
        for bill in await bill_crud.list_all():
            if bill.supplier_ref == supplier_ref:
                return True
        return False

    async def _location_by_name(self, name: str):
        location = await self.location_crud.get_active_by_name_insensitive(name)
        if location is None:
            raise NotFoundError(f"Location {name} not found")
        return location

    async def _ensure_transaction(self) -> None:
        if not self.db.in_transaction():
            await self.db.execute(select(1))
