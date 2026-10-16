from __future__ import annotations

import csv
from decimal import Decimal
from pathlib import Path

import pytest
from openpyxl import Workbook
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.commands.import_cin7 import assert_safe_database_url
from app.models.archive_credit_note import ArchiveCreditNote
from app.models.bill import Bill
from app.models.cin7_party import SupplierContact
from app.models.credit_note import CreditNote
from app.models.inventory import LocationStock
from app.models.journal import JournalEntry
from app.models.purchase_order import PurchaseOrder
from app.models.sku import Sku
from app.models.sku_bom_line import SkuBomLine
from app.models.tax_invoice import TaxInvoice
from app.services.cin7_import.parse import assign_barcodes, fill_down, realign_status_row
from app.services.cin7_import.load import run_import


def _write_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def _write_xlsx(path: Path, header: list[str], rows: list[list[object]]) -> None:
    book = Workbook()
    sheet = book.active
    sheet.title = "All"
    sheet.append(header)
    for row in rows:
        sheet.append(row)
    book.save(path)


def _fixture_dir(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    _write_csv(
        root / "PaymentTerm_fixture.csv",
        ["Name", "Days", "Method", "DueNextMonth", "PaymentTermActive", "PaymentTermDefault"],
        [["COD", "0", "1", "0", "True", "False"]],
    )
    _write_csv(
        root / "TaxationRules_fixture.csv",
        [
            "Description",
            "Tax1",
            "AccountCode",
            "Inclusive",
            "IsActive",
            "EffectivePercentExclusive",
            "EffectivePercentInclusive",
            "EffectivePercent",
        ],
        [
            [
                "Standard Rate Sales",
                "OUTPUT3",
                "9500/000",
                "False",
                "True",
                "15.00",
                "13.04",
                "15.00",
            ]
        ],
    )
    _write_csv(
        root / "ChartOfAccounts_fixture.csv",
        ["*Code", "*Name", "*Class", "*Type", "*SystemAccount", "*Status"],
        [
            ["1000/000", "Sales", "REVENUE", "SALES", "", "ACTIVE"],
            ["8000/000", "Accounts Receivable", "ASSET", "CURRENT", "DEBTORS", "ACTIVE"],
        ],
    )
    _write_csv(
        root / "Suppliers_fixture.csv",
        ["Name", "Status", "Currency", "PaymentTerm", "ContactName", "ContactDefault"],
        [
            ["Fixture Mill", "Active", "USD", "COD", "Ada", "True"],
            ["Fixture Mill", "Active", "USD", "COD", "Bea", "False"],
        ],
    )
    _write_csv(
        root / "SupplierContacts_fixture.csv",
        ["Supplier", "Contact", "Phone", "Email", "Default"],
        [["Fixture Mill", "Ada", "0100000000", "ada@example.com", "True"]],
    )
    _write_csv(
        root / "SupplierAddresses_fixture.csv",
        ["Name", "AddressType", "AddressLine1"],
        [["Fixture Mill", "Billing", "1 Mill Road"]],
    )
    _write_csv(
        root / "Customers_fixture.csv",
        [
            "Name",
            "Status",
            "Currency",
            "PaymentTerm",
            "PriceTier",
            "CreditLimit",
            "TaxNumber",
            "Phone",
            "Email",
        ],
        [
            ["Fixture Buyer", "ZAR", "COD", "Standard Rate Sales", "0", "0.00", "", "", ""],
            ["Fixture Trade", "Active", "ZAR", "COD", "Wholesale", "0.00", "4120000000", "", ""],
        ],
    )
    _write_csv(
        root / "CustomerContacts_fixture.csv",
        ["Customer", "Contact", "Phone", "MobilePhone", "Email", "Default"],
        [
            ["Fixture Buyer", "Pat", "", "0820000000", "pat@example.com", "True"],
            ["Fixture Buyer", "Sam", "0110000000", "", "sam@example.com", "False"],
        ],
    )
    _write_csv(
        root / "CustomerAddresses_fixture.csv",
        [
            "Name",
            "AddressType",
            "AddressDefaultForType",
            "AddressLine1",
            "AddressLine2",
            "City",
            "State",
            "Postcode",
            "Country",
        ],
        [
            [
                "Fixture Buyer",
                "Shipping",
                "True",
                "9 Side Street",
                "",
                "Johannesburg",
                "Gauteng",
                "2000",
                "South Africa",
            ],
            [
                "Fixture Buyer",
                "Billing",
                "True",
                "1 Main Road",
                "",
                "Johannesburg",
                "Gauteng",
                "2001",
                "South Africa",
            ],
        ],
    )
    _write_csv(
        root / "LocationsWithBins_fixture.csv",
        ["Name", "Default", "Deprecated", "BinGroup"],
        [
            ["Fixture DC", "Yes", "No", ""],
            ["Fixture DC: Showroom", "No", "No", ""],
        ],
    )
    _write_csv(
        root / "InventoryList_fixture.csv",
        [
            "ProductCode",
            "Name",
            "Category",
            "Barcode",
            "MinimumBeforeReorder",
            "CartonQuantity",
            "LastSuppliedBy",
            "SupplierProductCode",
            "PriceTier1",
            "PriceTier2",
            "PriceTier7",
        ],
        [
            [
                "CHAIR-1",
                "Chair",
                "Dining",
                "",
                "2.0000",
                "0.0000",
                "Fixture Mill",
                "MILL-1",
                "100.00",
                "80.00",
                "0.0000",
            ],
            [
                "LAMP-1",
                "Lamp",
                "Decor",
                "SHARED",
                "0.0000",
                "2.0000",
                "Missing Mill",
                "SUP-LONG",
                "50.00",
                "40.00",
                "0.0000",
            ],
            [
                "VASE-1",
                "Vase",
                "Decor",
                "SHARED",
                "0.0000",
                "1.0000",
                "",
                "",
                "10.00",
                "0.00",
                "0.0000",
            ],
        ],
    )
    _write_csv(
        root / "SimplePrices_fixture.csv",
        ["ProductCode", "PriceTier1", "PriceTier2"],
        [["CHAIR-1", "100.00", "80.00"]],
    )
    _write_csv(
        root / "MarkupPrices_fixture.csv",
        ["ProductSKU", "PriceTier", "Value"],
        [["CHAIR-1", "1", "0.000000"]],
    )
    _write_csv(
        root / "ProductPriceBySupplier_fixture.csv",
        ["SKU", "Supplier", "SupplierSKU", "LatestPrice", "FixedPrice"],
        [["CHAIR-1", "Fixture Mill", "MILL-1", "70.0000", "70.0000"]],
    )
    _write_csv(
        root / "AssemblyBOM_fixture.csv",
        ["ProductSKU", "ComponentSKU", "Quantity"],
        [
            ["CHAIR-1", "LAMP-1", "2.0000000000"],
            ["CHAIR-1", "VASE-1", "0.5000000000"],
        ],
    )
    _write_csv(
        root / "StockOnHand_fixture.csv",
        ["ProductCode", "Quantity", "AverageCost", "Location", "Bin"],
        [["CHAIR-1", "2.4", "10.0000", "Fixture DC", "Showroom"]],
    )
    _write_csv(
        root / "AvailabilityReport_fixture.csv",
        ["SKU", "OnHand"],
        [["CHAIR-1", "99"]],
    )
    _write_csv(
        root / "SmartReorderingConfiguration_fixture.csv",
        ["SKU", "Lead"],
        [["CHAIR-1", "14"]],
    )
    _write_csv(
        root / "StockReorderlocations_fixture.csv",
        ["ProductSKU", "Location", "MinimumBeforeReorder"],
        [["CHAIR-1", "Fixture DC", "4"]],
    )
    _write_xlsx(
        root / "Sale_Order_Details_fixture.xlsx",
        ["SKU", "Product", "Order #", "Order date", "Customer", "Status", "Quantity Total"],
        [
            ["CHAIR-1", "Chair", "SO-100", "2024-01-02", "Fixture Buyer", "Completed", 1],
            ["", "", "SO-100", "2024-01-02", "Fixture Buyer", "Completed", 1],
            ["LAMP-1", "Lamp", "SO-101", "2024-01-02", "Fixture Walkin", "Completed", 1],
        ],
    )
    _write_xlsx(
        root / "Sale Documents_fixture.xlsx",
        ["Document #", "Customer", "Date", "SKU", "Product", "Quantity", "Amount", "Tax", "Total"],
        [
            ["INV-9001", "Fixture Buyer", "2024-01-03", "CHAIR-1", "Chair", 1, 100, 15, 115],
            ["CR-9001", "Fixture Buyer", "2024-01-04", "CHAIR-1", "Chair", -1, -100, -15, -115],
        ],
    )
    _write_xlsx(
        root / "Sales_by_Product_fixture.xlsx",
        ["SKU", "Product", "Order #", "Document #", "Quantity", "Invoice"],
        [["CHAIR-1", "Chair", "SO-100", "INV-9001", 1, 100]],
    )
    _write_xlsx(
        root / "Purchase_Order_Details_fixture.xlsx",
        [
            "SKU",
            "Product",
            "PO #",
            "PO date",
            "Invoice #",
            "Invoice date",
            "Status",
            "Supplier",
            "Quantity",
            "Cost",
            "Total",
        ],
        [
            [
                "CHAIR-1",
                "Chair",
                "PO-9001",
                "2024-01-01",
                "BILL-1",
                "2024-01-05",
                "Received",
                "Fixture Mill",
                5,
                70,
                350,
            ],
            [
                "LAMP-1",
                "Lamp",
                "PO-9001",
                "2024-01-01",
                "BILL-1",
                "2024-01-05",
                "Received",
                "Fixture Mill",
                1,
                0,
                0,
            ],
            [
                "LAMP-1",
                "Lamp",
                "PO-9002",
                "2024-01-01",
                "BILL-2",
                "2024-01-05",
                "Received",
                "Fixture Yard",
                1,
                10,
                10,
            ],
        ],
    )
    _write_xlsx(
        root / "Purchase_Invoice_Details_fixture.xlsx",
        [
            "SKU",
            "Product",
            "PO #",
            "Invoice #",
            "Invoice date",
            "Status",
            "Supplier",
            "Quantity",
            "Price",
            "Total",
        ],
        [
            [
                "CHAIR-1",
                "Chair",
                "PO-9001",
                "BILL-1",
                "2024-01-05",
                "Completed",
                "Fixture Mill",
                5,
                70,
                350,
            ],
        ],
    )
    return root


@pytest.mark.no_db
def test_fill_down_carries_sku_and_name() -> None:
    header = ["SKU", "Product", "Order #"]
    rows = [
        ["CHAIR-1", "Chair", "SO-1"],
        ["", "", "SO-2"],
        ["LAMP-1", "Lamp", "SO-3"],
    ]
    filled_rows, count = fill_down(header, rows)
    assert count == 2
    assert filled_rows[1] == ["CHAIR-1", "Chair", "SO-2"]
    assert filled_rows[2][0] == "LAMP-1"


@pytest.mark.no_db
def test_customer_status_shift_inserts_active() -> None:
    header = ["Name", "Status", "Currency", "PaymentTerm", "PriceTier"]
    # Status holds the currency and PriceTier holds 0 until the missing Status cell is inserted.
    shifted = ["Fixture Buyer", "ZAR", "COD", "Wholesale", "0"]
    cells, did = realign_status_row(header, shifted)
    assert did is True
    assert cells == ["Fixture Buyer", "Active", "ZAR", "COD", "Wholesale"]

    aligned = ["Fixture Trade", "Active", "ZAR", "COD", "Wholesale"]
    cells, did = realign_status_row(header, aligned)
    assert did is False
    assert cells[1] == "Active"
    assert cells[4] == "Wholesale"


@pytest.mark.no_db
def test_assign_barcodes_keeps_one_shared_code_and_generates_the_rest() -> None:
    assigned = assign_barcodes(
        [("LAMP-1", "SHARED"), ("VASE-1", "SHARED"), ("CHAIR-1", "")],
        taken=set(),
    )
    assert assigned["LAMP-1"] == ("SHARED", False)
    assert assigned["VASE-1"][1] is True
    assert assigned["CHAIR-1"] == ("CIN7-CHAIR-1", True)
    assert len({barcode for barcode, _generated in assigned.values()}) == 3


@pytest.mark.no_db
def test_database_url_guard_refuses_marrow_and_remote_without_develop_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(SystemExit):
        assert_safe_database_url("postgresql+asyncpg://health:health@localhost/healthtracker")
    with pytest.raises(SystemExit):
        assert_safe_database_url("postgresql+asyncpg://u:p@firstout.example/firstout")
    monkeypatch.setenv("FIRSTOUT_CIN7_IMPORT_TARGET", "develop")
    assert_safe_database_url("postgresql+asyncpg://u:p@firstout.example/firstout")
    assert_safe_database_url("postgresql+asyncpg://firstout:firstout@127.0.0.1:5432/firstout")
    monkeypatch.setenv("FIRSTOUT_CIN7_IMPORT_TARGET", "firstout")
    assert_safe_database_url("postgresql+asyncpg://u:p@firstout.example/firstout")
    monkeypatch.setenv("FIRSTOUT_CIN7_IMPORT_TARGET", "marrow")
    with pytest.raises(SystemExit):
        assert_safe_database_url("postgresql+asyncpg://u:p@firstout.example/firstout")


@pytest.mark.asyncio
async def test_cin7_import_is_idempotent_and_does_not_post(async_db, tmp_path: Path) -> None:
    export_dir = _fixture_dir(tmp_path / "cin7")
    journals_before = await async_db.scalar(select(func.count()).select_from(JournalEntry))

    first = await run_import(async_db, export_dir)
    await async_db.commit()

    chair = (await async_db.execute(select(Sku).where(Sku.our_ref == "CHAIR-1"))).scalar_one()
    assert chair.our_barcode == "CIN7-CHAIR-1"
    assert chair.design == "cin7:CHAIR-1"
    assert chair.fabric == "-"
    assert chair.retail_ex_vat == Decimal("100.00")
    assert chair.wholesale_ex_vat == Decimal("80.00")
    assert chair.reorder_min == 2
    assert chair.carton_count == 1
    assert chair.preferred_supplier_id is not None

    lamp = (await async_db.execute(select(Sku).where(Sku.our_ref == "LAMP-1"))).scalar_one()
    vase = (await async_db.execute(select(Sku).where(Sku.our_ref == "VASE-1"))).scalar_one()
    assert lamp.our_barcode == "SHARED"
    assert vase.our_barcode.startswith("CIN7-")
    assert lamp.carton_count == 2

    stock = (
        await async_db.execute(select(LocationStock).where(LocationStock.sku_id == chair.id))
    ).scalar_one()
    assert stock.on_hand == 2

    bom = (await async_db.execute(select(SkuBomLine))).scalars().all()
    assert sorted(line.qty for line in bom) == [Decimal("0.5"), Decimal("2")]

    invoice = (
        await async_db.execute(select(TaxInvoice).where(TaxInvoice.invoice_number == "INV-9001"))
    ).scalar_one()
    assert invoice.is_archive is True
    assert invoice.total_inc_vat == Decimal("115.00")
    credit = await async_db.scalar(
        select(func.count()).select_from(TaxInvoice).where(TaxInvoice.invoice_number == "CR-9001")
    )
    assert credit == 0
    archive_credit = (
        await async_db.execute(
            select(ArchiveCreditNote)
            .where(ArchiveCreditNote.document_number == "CR-9001")
            .options(selectinload(ArchiveCreditNote.lines))
        )
    ).scalar_one()
    assert archive_credit.lines
    assert await async_db.scalar(select(func.count()).select_from(CreditNote)) == 0

    purchase = (
        await async_db.execute(select(PurchaseOrder).where(PurchaseOrder.po_number == "PO-9001"))
    ).scalar_one()
    assert purchase.is_archive is True
    assert purchase.status.value == "received"
    assert stock.on_hand == 2

    bill = (await async_db.execute(select(Bill).where(Bill.bill_number == "BILL-1"))).scalar_one()
    assert bill.is_archive is True
    assert bill.currency == "USD"
    assert bill.fx_to_zar == Decimal("0")
    assert bill.amount_zar == Decimal("0")
    assert bill.amount_foreign == Decimal("350.00")
    assert bill.fx_rate_known is False

    journals_after = await async_db.scalar(select(func.count()).select_from(JournalEntry))
    assert journals_after == journals_before

    assert first.entity("sku").created == 3
    assert first.entity("sku_bom_line").created == 2
    assert (
        first.entity("po_line").reasons["purchase order factory unit amount must be greater than 0"]
        == 1
    )
    assert first.entity("customer").reasons["stub customer created from a document name"] == 1
    assert first.entity("supplier").reasons["stub supplier created from a document name"] == 1
    assert first.entity("archive_credit_note").created == 1
    assert first.entity("supplier_contact").created == 1
    assert first.entity("supplier_address").created == 1
    assert first.entity("customer_contact").created >= 1
    assert first.entity("customer_address").created >= 1
    assert await async_db.scalar(select(func.count()).select_from(SupplierContact)) == 1
    assert first.customer_rows_realigned == 1
    assert first.filled_down["Sale_Order_Details"] == 2

    second = await run_import(async_db, export_dir)
    await async_db.commit()
    assert second.entity("sku").created == 0
    assert second.entity("tax_invoice").created == 0
    assert second.entity("purchase_order").created == 0
    assert second.entity("bill").created == 0
    assert second.entity("customer").created == 0
    assert second.entity("supplier").created == 0
    changed = {
        name: (result.created, result.updated)
        for name, result in second.entities.items()
        if result.created or result.updated
    }
    assert changed == {}
    sku_count = await async_db.scalar(
        select(func.count()).select_from(Sku).where(Sku.our_ref == "CHAIR-1")
    )
    assert sku_count == 1
