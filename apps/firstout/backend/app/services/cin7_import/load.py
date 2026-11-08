from __future__ import annotations

import asyncio
import datetime
import uuid
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.account import Account, AccountType, default_tax_treatment
from app.models.archive_credit_note import ArchiveCreditNote, ArchiveCreditNoteLine
from app.models.bill import Bill, BillLine
from app.models.cin7_party import (
    CustomerAddress,
    CustomerContact,
    SupplierAddress,
    SupplierContact,
)
from app.models.customer import Customer
from app.models.inventory import LocationStock
from app.models.journal import JournalEntry
from app.models.location import Location, LocationType
from app.models.location_bin import BinStock, LocationBin, new_floor_bin
from app.models.payment_term import PaymentTerm
from app.models.price_list import PriceList, PriceListItem
from app.models.purchase_order import PoLine, PurchaseOrder, PurchaseOrderStatus
from app.models.sales_order import SalesOrder, SalesOrderLine, SalesOrderStatus
from app.models.sku import Sku
from app.models.sku_bom_line import SkuBomLine
from app.models.sku_supplier_price import SkuSupplierPrice
from app.models.supplier import Supplier
from app.models.tax_invoice import InvoiceLine, TaxInvoice
from app.models.tax_rule import TaxRule
from app.services.cin7_import.parse import (
    as_bool,
    assign_barcodes,
    generated_barcode_rows,
    carton_count,
    clip,
    find_file,
    integral_qty,
    money,
    NamedSkuPrices,
    named_sku_prices,
    parse_date,
    price_warnings,
    read_csv_records,
    read_xlsx_all,
    reorder_min,
    tier_amount_ex_vat,
    tier_price_list_name,
)
from app.services.cin7_import.children import (
    address_payload,
    contact_payload,
    upsert_children,
)
from app.services.cin7_import.report import EntityResult, ImportReport
from app.services.pricing import (
    classification_from_cin7_tier,
    customer_type_for_classification,
    shows_prices_including_vat,
)

ASSUMPTIONS = [
    "Cin7 PriceTier1 is Stockist ex VAT, PriceTier2 is Wholesale ex VAT, "
    "PriceTier3 is Decorator ex VAT, and PriceTier4 is Retail including 15% VAT. "
    "Retail is stored ex VAT (inc / 1.15, half-up to the cent). "
    "The same four amounts are written to price lists Cin7 Stockist, Cin7 Wholesale, "
    "Cin7 Decorator, and Cin7 Retail. Those lists, and older Cin7 Tier N lists, do not "
    "override price_classification. Customer PriceTier is stored as price_classification "
    "and selects that SKU price. price_tier keeps the Cin7 label.",
    "New SKUs get design cin7:{ProductCode} and fabric '-'. Later runs leave design and fabric as they are.",
    "Blank barcodes, and every barcode shared by more than one product, are replaced with CIN7-{ProductCode}. "
    "The lowest product code keeps a shared Cin7 barcode.",
    "Sales orders, tax invoices, purchase orders, and bills are archive rows. "
    "The import does not write journals or move stock for them.",
    "Bills in a currency other than ZAR keep the currency and foreign amount, with "
    "fx_rate_known false. The export has no exchange rate, so the ZAR value is unknown.",
    "On-hand quantities come from StockOnHand only. A received purchase order does not increase stock.",
    "Archive invoices are left out of VAT, aged receivables, and overdue balances. "
    "Sales-by-SKU and SKU criticality still include them when the date range covers the invoice.",
    "Customer PriceTier Stockist, Wholesale, and Decorator set price_classification and customer_type trade. "
    "Retail and any other tier set price_classification Retail and customer_type retail. "
    "price_tier keeps the original Cin7 text.",
    "LocationsWithBins has an empty BinGroup. Each location gets the required FLOOR bin. "
    "StockOnHand bin names are matched to location names.",
]

CLASS_MAP = {
    "ASSET": AccountType.ASSET,
    "LIABILITY": AccountType.LIABILITY,
    "EQUITY": AccountType.EQUITY,
    "REVENUE": AccountType.INCOME,
    "EXPENSE": AccountType.EXPENSE,
}
PO_STATUS = {
    "completed": PurchaseOrderStatus.RECEIVED,
    "fully billed": PurchaseOrderStatus.RECEIVED,
    "received": PurchaseOrderStatus.RECEIVED,
    "credited": PurchaseOrderStatus.RECEIVED,
    "receiving": PurchaseOrderStatus.LANDED,
    "invoiced": PurchaseOrderStatus.LANDED,
    "ordered": PurchaseOrderStatus.OPEN,
    "ordering": PurchaseOrderStatus.OPEN,
}
SO_STATUS = {
    "completed": SalesOrderStatus.INVOICED,
    "invoiced": SalesOrderStatus.INVOICED,
    "credited": SalesOrderStatus.INVOICED,
    "ordered": SalesOrderStatus.OPEN,
    "packed": SalesOrderStatus.OPEN,
    "shipping": SalesOrderStatus.OPEN,
}
ZERO = Decimal("0.00")
FX_ONE = Decimal("1.000000")
FX_ZERO = Decimal("0.000000")


def _key(value: str) -> str:
    return value.strip().lower()


def _utc(day: datetime.date) -> datetime.datetime:
    return datetime.datetime(day.year, day.month, day.day, tzinfo=datetime.timezone.utc)


def _dec_eq(left: Optional[Decimal], right: Optional[Decimal]) -> bool:
    if left is None and right is None:
        return True
    if left is None or right is None:
        return False
    return Decimal(left) == Decimal(right)


def _note_price_changes(
    report: ImportReport,
    current: Optional[Sku],
    prices: NamedSkuPrices,
) -> None:
    """Count tier prices that would change. A new SKU counts each price it sets."""
    pairs = (
        ("stockist", None if current is None else current.stockist_ex_vat, prices.stockist_ex_vat),
        (
            "wholesale",
            None if current is None else current.wholesale_ex_vat,
            prices.wholesale_ex_vat,
        ),
        (
            "decorator",
            None if current is None else current.decorator_ex_vat,
            prices.decorator_ex_vat,
        ),
        ("retail", None if current is None else current.retail_ex_vat, prices.retail_ex_vat),
    )
    for tier, old, new in pairs:
        changed = new is not None if current is None else not _dec_eq(old, new)
        if changed:
            report.price_changes[tier] = report.price_changes.get(tier, 0) + 1


def _group(rows: list[dict[str, str]], column: str) -> list[tuple[str, list[dict[str, str]]]]:
    grouped: dict[str, list[dict[str, str]]] = {}
    order: list[str] = []
    for row in rows:
        key = row.get(column, "").strip()
        if key not in grouped:
            grouped[key] = []
            order.append(key)
        grouped[key].append(row)
    return [(key, grouped[key]) for key in order]


def _pick_contact_row(rows: list[dict[str, str]], flag: str) -> dict[str, str]:
    defaults = [row for row in rows if as_bool(row.get(flag, ""))]
    if defaults:
        return defaults[0]
    return rows[0]


def _phone(row: dict[str, str]) -> Optional[str]:
    mobile = clip(row.get("MobilePhone"), 32)
    if mobile:
        return mobile
    return clip(row.get("Phone"), 32)


def _email(row: dict[str, str]) -> Optional[str]:
    email = clip(row.get("Email"), 255)
    if email is None or "@" not in email:
        return None
    return email


def _address_text(row: dict[str, str]) -> str:
    parts = [
        row.get("AddressLine1", "").strip(),
        row.get("AddressLine2", "").strip(),
        " ".join(
            part
            for part in (
                row.get("City", "").strip(),
                row.get("State", "").strip(),
                row.get("Postcode", "").strip(),
            )
            if part
        ),
        row.get("Country", "").strip(),
    ]
    return "\n".join(part for part in parts if part)[:4000]


def _address_rank(row: dict[str, str]) -> tuple[int, int]:
    kind = row.get("AddressType", "").strip().lower()
    billing = 1 if kind == "billing" else 0
    default = 1 if as_bool(row.get("AddressDefaultForType", "")) else 0
    return (billing, default)


def _location_type(name: str, is_default: bool) -> LocationType:
    if is_default or "warehouse" in name.lower():
        return LocationType.WAREHOUSE
    return LocationType.SHOWROOM


def _match_location(
    parent: str,
    bin_name: str,
    names: dict[str, uuid.UUID],
) -> Optional[uuid.UUID]:
    parent_key = _key(parent)
    bin_key = _key(bin_name)
    if bin_key:
        exact = f"{parent_key}: {bin_key}"
        if exact in names:
            return names[exact]
        suffix = f": {bin_key}"
        matches = [key for key in names if key.endswith(suffix)]
        if len(matches) == 1:
            return names[matches[0]]
    return names.get(parent_key)


class Cin7Loader:
    def __init__(self, session: AsyncSession, export_dir: Path) -> None:
        self.session = session
        self.export_dir = export_dir
        self.report = ImportReport(dry_run=True)
        self.suppliers: dict[str, Supplier] = {}
        self.customers: dict[str, Customer] = {}
        self.skus: dict[str, Sku] = {}
        self.locations: dict[str, Location] = {}
        self.supplier_currency: dict[str, str] = {}
        self.payment_days: dict[str, int] = {}
        self._credit_rows: list[dict[str, str]] = []
        self._workbooks: dict[Path, tuple[list[dict[str, str]], int]] = {}

    def _result(self, name: str) -> EntityResult:
        return self.report.entity(name)

    async def run(self) -> ImportReport:
        self.report.assumptions = list(ASSUMPTIONS)
        await self._load_payment_terms()
        await self._load_tax_rules()
        await self._load_accounts()
        await self._load_suppliers()
        await self._load_customers()
        await self._ensure_document_parties()
        await self._load_customer_contacts()
        await self._load_customer_addresses()
        await self._load_supplier_children()
        await self._load_locations()
        await self._load_skus()
        await self._load_price_lists()
        await self._note_simple_prices()
        await self._note_markup_prices()
        await self._load_supplier_prices()
        await self._load_bom()
        await self._load_stock()
        await self._load_sales_orders()
        await self._load_invoices()
        await self._load_archive_credit_notes()
        await self._link_orders_to_invoices()
        await self._load_purchase_orders()
        await self._load_bills()
        await self._note_unused_files()
        journals = await self.session.scalar(select(JournalEntry.id).limit(1))
        if journals is not None:
            self.report.assumptions.append(
                "Journal rows already existed before this import. This run did not add any."
            )
        return self.report

    async def _load_payment_terms(self) -> None:
        result = self._result("payment_term")
        path = find_file(self.export_dir, "PaymentTerm", ".csv")
        if path is None:
            result.skip("PaymentTerm file not found")
            return
        rows, _shifted = await self._read_csv(path)
        existing = {
            _key(row.name): row for row in (await self.session.scalars(select(PaymentTerm))).all()
        }
        for row in rows:
            name = clip(row.get("Name"), 255)
            if name is None:
                result.skip("payment term has no name")
                continue
            days_text = row.get("Days", "").strip() or "0"
            try:
                days = int(Decimal(days_text))
            except (ArithmeticError, ValueError):
                result.skip("payment term days are not an integer")
                continue
            payload = {
                "days": days,
                "method": (row.get("Method") or "")[:32],
                "due_next_month": as_bool(row.get("DueNextMonth", "")),
                "is_active": as_bool(row.get("PaymentTermActive", ""))
                or row.get("PaymentTermActive", "") == "",
                "is_default": as_bool(row.get("PaymentTermDefault", "")),
            }
            current = existing.get(_key(name))
            if current is None:
                current = PaymentTerm(name=name, **payload)
                self.session.add(current)
                existing[_key(name)] = current
                result.created += 1
            elif (
                current.days == payload["days"]
                and current.method == payload["method"]
                and current.due_next_month == payload["due_next_month"]
                and current.is_active == payload["is_active"]
                and current.is_default == payload["is_default"]
            ):
                result.unchanged += 1
            else:
                current.days = payload["days"]
                current.method = payload["method"]
                current.due_next_month = payload["due_next_month"]
                current.is_active = payload["is_active"]
                current.is_default = payload["is_default"]
                result.updated += 1
            self.payment_days[_key(name)] = days
        await self.session.flush()

    async def _load_tax_rules(self) -> None:
        result = self._result("tax_rule")
        path = find_file(self.export_dir, "TaxationRules", ".csv")
        if path is None:
            result.skip("TaxationRules file not found")
            return
        rows, _shifted = await self._read_csv(path)
        existing = {
            _key(row.name): row for row in (await self.session.scalars(select(TaxRule))).all()
        }
        for row in rows:
            name = clip(row.get("Description"), 255)
            if name is None:
                result.skip("tax rule has no name")
                continue
            percent = money(row.get("EffectivePercent")) or ZERO
            payload = {
                "tax_code": (row.get("Tax1") or "")[:64],
                "account_code": (row.get("AccountCode") or "")[:32],
                "inclusive": as_bool(row.get("Inclusive", "")),
                "is_active": as_bool(row.get("IsActive", "")),
                "percent": percent,
            }
            current = existing.get(_key(name))
            if current is None:
                current = TaxRule(name=name, **payload)
                self.session.add(current)
                existing[_key(name)] = current
                result.created += 1
            elif (
                current.tax_code == payload["tax_code"]
                and current.account_code == payload["account_code"]
                and current.inclusive == payload["inclusive"]
                and current.is_active == payload["is_active"]
                and _dec_eq(current.percent, payload["percent"])
            ):
                result.unchanged += 1
            else:
                for field_name, value in payload.items():
                    setattr(current, field_name, value)
                result.updated += 1
        await self.session.flush()

    async def _load_accounts(self) -> None:
        result = self._result("account")
        path = find_file(self.export_dir, "ChartOfAccounts", ".csv")
        if path is None:
            result.skip("ChartOfAccounts file not found")
            return
        rows, _shifted = await self._read_csv(path)
        existing = {row.code: row for row in (await self.session.scalars(select(Account))).all()}
        for row in rows:
            code = clip(row.get("*Code") or row.get("Code"), 16)
            name = clip(row.get("*Name") or row.get("Name"), 255)
            if code is None or name is None:
                result.skip("account is missing a code or name")
                continue
            class_name = (row.get("*Class") or row.get("Class") or "").strip().upper()
            account_type = CLASS_MAP.get(class_name)
            if account_type is None:
                result.skip(f"account class {class_name or '(blank)'} is not mapped")
                continue
            archived = (row.get("*Status") or row.get("Status") or "").strip().upper() == "ARCHIVED"
            is_bank = (row.get("*Type") or row.get("Type") or "").strip().upper() == "BANK"
            treatment = default_tax_treatment(account_type)
            current = existing.get(code)
            if current is not None and current.is_system:
                result.unchanged += 1
                result.note("system account left unchanged")
                continue
            if current is None:
                current = Account(
                    code=code,
                    name=name,
                    type=account_type,
                    is_system=False,
                    is_archived=archived,
                    is_bank=is_bank,
                    tax_treatment=treatment,
                )
                self.session.add(current)
                existing[code] = current
                result.created += 1
            elif (
                current.name == name
                and current.type == account_type
                and current.is_archived == archived
                and current.is_bank == is_bank
                and current.tax_treatment == treatment
            ):
                result.unchanged += 1
            else:
                current.name = name
                current.type = account_type
                current.is_archived = archived
                current.is_bank = is_bank
                current.tax_treatment = treatment
                result.updated += 1
        await self.session.flush()

    async def _load_suppliers(self) -> None:
        result = self._result("supplier")
        path = find_file(self.export_dir, "Suppliers_", ".csv")
        if path is None:
            result.skip("Suppliers file not found")
            return
        rows, shifted = await self._read_csv(path, realign=True)
        self.report.supplier_rows_realigned = shifted
        chosen, folded = _collapse(rows, "Name", "ContactDefault")
        if folded:
            result.note("duplicate supplier name rows merged on the name", folded)
        existing = {
            _key(row.name): row for row in (await self.session.scalars(select(Supplier))).all()
        }
        # Document stubs from an earlier run are not in the supplier file. Keep them
        # addressable so a second import updates the document instead of inserting again.
        for key, supplier in existing.items():
            self.suppliers[key] = supplier
            self.supplier_currency[key] = supplier.default_currency
        for row in chosen:
            name = clip(row.get("Name"), 255)
            if name is None:
                result.skip("supplier has no name")
                continue
            currency = (row.get("Currency") or "USD").strip().upper()[:3] or "USD"
            current = existing.get(_key(name))
            if current is None:
                current = Supplier(name=name, default_currency=currency)
                self.session.add(current)
                existing[_key(name)] = current
                result.created += 1
            elif current.default_currency == currency:
                result.unchanged += 1
            else:
                current.default_currency = currency
                result.updated += 1
            self.suppliers[_key(name)] = current
            self.supplier_currency[_key(name)] = currency
        await self.session.flush()

    async def _ensure_supplier(self, name: str) -> Optional[Supplier]:
        key = _key(name)
        if not key:
            return None
        found = self.suppliers.get(key)
        if found is not None:
            return found
        found = Supplier(name=clip(name, 255) or name[:255], default_currency="USD")
        self.session.add(found)
        await self.session.flush()
        self.suppliers[key] = found
        self.supplier_currency[key] = "USD"
        self._result("supplier").created += 1
        self._result("supplier").note("stub supplier created from a document name")
        return found

    async def _load_customers(self) -> None:
        result = self._result("customer")
        path = find_file(self.export_dir, "Customers_", ".csv")
        if path is None:
            result.skip("Customers file not found")
            return
        rows, shifted = await self._read_csv(path, realign=True)
        self.report.customer_rows_realigned = shifted
        if shifted == 0:
            self.report.assumptions.append(
                "Customer Status, Currency, and PriceTier lined up in this export "
                "(Status was not a currency code)."
            )
        chosen, folded = _collapse(rows, "Name", "ContactDefault")
        if folded:
            result.note("duplicate customer name rows merged on the name", folded)
        existing = {
            _key(row.name): row for row in (await self.session.scalars(select(Customer))).all()
        }
        # Same as suppliers: a document-only name already stored must not be inserted again.
        self.customers.update(existing)
        for row in chosen:
            await self._upsert_customer(existing, row, result)
        await self.session.flush()

    async def _upsert_customer(
        self,
        existing: dict[str, Customer],
        row: dict[str, str],
        result: EntityResult,
    ) -> None:
        name = clip(row.get("Name"), 255)
        if name is None:
            result.skip("customer has no name")
            return
        tier = clip(row.get("PriceTier"), 64) or "standard"
        if tier == "0":
            result.note("price tier cell was 0 and was stored as standard")
            tier = "standard"
        classification = classification_from_cin7_tier(None if tier == "standard" else tier)
        credit = money(row.get("CreditLimit"))
        if credit is not None and credit <= 0:
            credit = None
        days = self.payment_days.get(_key(row.get("PaymentTerm", "")))
        status = row.get("Status", "").strip().lower()
        payload = {
            "email": _email(row),
            "phone": _phone(row),
            "vat_number": clip(row.get("TaxNumber"), 64),
            "customer_type": customer_type_for_classification(classification),
            "price_classification": classification,
            "price_tier": tier,
            "credit_limit": credit,
            "on_hold": bool(status) and status != "active",
            "payment_terms_days": days,
        }
        current = existing.get(_key(name))
        if current is None:
            current = Customer(name=name, **payload)
            self.session.add(current)
            existing[_key(name)] = current
            result.created += 1
        else:
            # The contact file is applied after this and is what remains on the row.
            # Keep the stored phone and email so the two files do not rewrite each other.
            payload["phone"] = current.phone
            payload["email"] = current.email
            if _customer_same(current, payload):
                result.unchanged += 1
            else:
                for field_name, value in payload.items():
                    setattr(current, field_name, value)
                result.updated += 1
        self.customers[_key(name)] = current

    async def _ensure_customer(self, name: str) -> Optional[Customer]:
        key = _key(name)
        if not key:
            return None
        found = self.customers.get(key)
        if found is not None:
            return found
        found = Customer(name=clip(name, 255) or name[:255])
        self.session.add(found)
        await self.session.flush()
        self.customers[key] = found
        self._result("customer").created += 1
        self._result("customer").note("stub customer created from a document name")
        return found

    async def _read_csv(
        self, path: Path, realign: bool = False
    ) -> tuple[list[dict[str, str]], int]:
        return await asyncio.to_thread(read_csv_records, path, realign)

    async def _read_xlsx(self, path: Path) -> tuple[list[dict[str, str]], int]:
        cached = self._workbooks.get(path)
        if cached is None:
            cached = await asyncio.to_thread(read_xlsx_all, path)
            self._workbooks[path] = cached
        return cached

    async def _ensure_document_parties(self) -> None:
        """Create customer/supplier stubs named only on documents before anything links to them.

        Contacts, SKU LastSuppliedBy, and documents then resolve on the first run, so a
        second run of the same export changes nothing.
        """
        for prefix, column, ensure in (
            ("Sale_Order_Details", "Customer", self._ensure_customer),
            ("Sale_Documents", "Customer", self._ensure_customer),
            ("Purchase_Order_Details", "Supplier", self._ensure_supplier),
            ("Purchase_Invoice_Details", "Supplier", self._ensure_supplier),
        ):
            path = find_file(self.export_dir, prefix, ".xlsx")
            if path is None:
                continue
            records, _filled = await self._read_xlsx(path)
            for name in sorted({row.get(column, "").strip() for row in records} - {""}):
                await ensure(name)

    async def _load_customer_contacts(self) -> None:
        # customer_primary_contact: the default contact's phone/email on the customer row.
        # customer_contact: every contact row in customer_contacts.
        result = self._result("customer_primary_contact")
        path = find_file(self.export_dir, "CustomerContacts", ".csv")
        if path is None:
            result.skip("CustomerContacts file not found")
            return
        rows, _shifted = await self._read_csv(path)
        grouped: dict[str, list[dict[str, str]]] = {}
        for row in rows:
            key = _key(row.get("Customer", ""))
            if not key:
                result.skip("contact has no customer")
                continue
            grouped.setdefault(key, []).append(row)
        for key, group in grouped.items():
            customer = self.customers.get(key)
            if customer is None:
                result.skip("contact customer is not in the customer export", len(group))
                continue
            chosen = _pick_contact_row(group, "Default")
            phone = _phone(chosen)
            email = _email(chosen)
            changed = False
            if phone and customer.phone != phone:
                customer.phone = phone
                changed = True
            if email and customer.email != email:
                customer.email = email
                changed = True
            if changed:
                result.updated += 1
            else:
                result.unchanged += 1
        await self.session.flush()
        await upsert_children(
            self.session,
            model=CustomerContact,
            owner_field="customer_id",
            owners=self.customers,
            owner_key=_key,
            rows=rows,
            owner_column="Customer",
            build=lambda row: contact_payload(row, with_marketing=True),
            result=self._result("customer_contact"),
        )

    async def _load_customer_addresses(self) -> None:
        # customer_billing_address: the chosen address text on customers.billing_address.
        result = self._result("customer_billing_address")
        path = find_file(self.export_dir, "CustomerAddresses", ".csv")
        if path is None:
            result.skip("CustomerAddresses file not found")
            return
        rows, _shifted = await self._read_csv(path)
        grouped: dict[str, list[dict[str, str]]] = {}
        for row in rows:
            key = _key(row.get("Name", ""))
            if not key:
                result.skip("address has no customer")
                continue
            grouped.setdefault(key, []).append(row)
        for key, group in grouped.items():
            customer = self.customers.get(key)
            if customer is None:
                result.skip("address customer is not in the customer export", len(group))
                continue
            chosen = max(group, key=_address_rank)
            text = _address_text(chosen)
            if text and customer.billing_address != text:
                customer.billing_address = text
                result.updated += 1
            else:
                result.unchanged += 1
        await self.session.flush()
        await upsert_children(
            self.session,
            model=CustomerAddress,
            owner_field="customer_id",
            owners=self.customers,
            owner_key=_key,
            rows=rows,
            owner_column="Name",
            build=address_payload,
            result=self._result("customer_address"),
        )

    async def _load_supplier_children(self) -> None:
        for prefix, entity, model, build in (
            ("SupplierContacts", "supplier_contact", SupplierContact, None),
            ("SupplierAddresses", "supplier_address", SupplierAddress, address_payload),
        ):
            path = find_file(self.export_dir, prefix, ".csv")
            if path is None:
                self._result(entity).skip(f"{prefix} file not found")
                continue
            rows, _shifted = await self._read_csv(path)
            column = "Supplier" if model is SupplierContact else "Name"
            await upsert_children(
                self.session,
                model=model,
                owner_field="supplier_id",
                owners=self.suppliers,
                owner_key=_key,
                rows=rows,
                owner_column=column,
                build=build or (lambda row: contact_payload(row, with_marketing=False)),
                result=self._result(entity),
            )

    async def _load_locations(self) -> None:
        result = self._result("location")
        bins = self._result("location_bin")
        path = find_file(self.export_dir, "LocationsWithBins", ".csv")
        if path is None:
            result.skip("LocationsWithBins file not found")
            return
        rows, _shifted = await self._read_csv(path)
        existing = {
            _key(row.name): row for row in (await self.session.scalars(select(Location))).all()
        }
        bin_rows = {
            row.location_id: row
            for row in (
                await self.session.scalars(
                    select(LocationBin).where(LocationBin.is_default.is_(True))
                )
            ).all()
        }
        for row in rows:
            name = clip(row.get("Name"), 255)
            if name is None:
                result.skip("location has no name")
                continue
            is_default = row.get("Default", "").strip().lower() == "yes"
            archived = row.get("Deprecated", "").strip().lower() == "yes"
            loc_type = _location_type(name, is_default)
            if (row.get("BinGroup") or "").strip():
                bins.note("BinGroup value was not imported as a bin")
            current = existing.get(_key(name))
            if current is None:
                current = Location(name=name, type=loc_type, is_archived=archived)
                self.session.add(current)
                await self.session.flush()
                floor = new_floor_bin(current.id)
                self.session.add(floor)
                bin_rows[current.id] = floor
                existing[_key(name)] = current
                result.created += 1
                bins.created += 1
            else:
                same = current.type == loc_type and current.is_archived == archived
                if same:
                    result.unchanged += 1
                else:
                    current.type = loc_type
                    current.is_archived = archived
                    result.updated += 1
                if current.id not in bin_rows:
                    floor = new_floor_bin(current.id)
                    self.session.add(floor)
                    bin_rows[current.id] = floor
                    bins.created += 1
                else:
                    bins.unchanged += 1
            self.locations[_key(name)] = current
        if bins.created == 0 and not rows:
            bins.skip("no location rows")
        elif all(not (row.get("BinGroup") or "").strip() for row in rows):
            bins.note("BinGroup is blank; FLOOR is the only bin")
        await self.session.flush()

    async def _load_skus(self) -> None:
        result = self._result("sku")
        path = find_file(self.export_dir, "InventoryList", ".csv")
        if path is None:
            result.skip("InventoryList file not found")
            return
        rows, _shifted = await self._read_csv(path)
        existing = {row.our_ref: row for row in (await self.session.scalars(select(Sku))).all()}
        taken = {row.our_barcode for row in existing.values()}
        pairs = [
            (row.get("ProductCode", "").strip(), row.get("Barcode", "").strip()) for row in rows
        ]
        pairs = [(code, barcode) for code, barcode in pairs if code]
        imported_codes = {code for code, _barcode in pairs}
        taken = {
            barcode
            for code, sku in existing.items()
            if code not in imported_codes
            for barcode in [sku.our_barcode]
        }
        assigned = assign_barcodes(pairs, taken)
        generated = sum(1 for _code, (_barcode, was_generated) in assigned.items() if was_generated)
        if generated:
            result.note("barcode generated because it was blank or duplicated", generated)
        self.report.barcode_replacements = generated_barcode_rows(pairs, assigned)
        designs = {
            (row.design.lower(), row.fabric.lower()): row.our_ref for row in existing.values()
        }
        original_barcodes = {code: sku.our_barcode for code, sku in existing.items()}
        for code, sku in list(existing.items()):
            if code in imported_codes:
                sku.our_barcode = f"T{uuid.uuid4().hex}"
        await self.session.flush()
        by_code = {
            row.get("ProductCode", "").strip(): row
            for row in rows
            if row.get("ProductCode", "").strip()
        }
        for code in sorted(by_code):
            row = by_code[code]
            self.report.warnings.extend(price_warnings(row))
            barcode, _generated = assigned[code]
            name = clip(row.get("Name"), 255) or code
            category = clip(row.get("Category"), 64)
            supplier_ref = clip(row.get("SupplierProductCode"), 128)
            supplier_name = row.get("LastSuppliedBy", "").strip()
            supplier = self.suppliers.get(_key(supplier_name)) if supplier_name else None
            if supplier_name and supplier is None:
                result.note("LastSuppliedBy did not match a supplier")
            prices = named_sku_prices(row)
            minimum = reorder_min(row.get("MinimumBeforeReorder", ""))
            cartons = carton_count(row.get("CartonQuantity", ""))
            current = existing.get(code)
            if current is None:
                design = f"cin7:{code}"[:255]
                fabric = "-"
                owner = designs.get((design.lower(), fabric.lower()))
                if owner is not None and owner != code:
                    design = f"cin7:{code}-2"[:255]
                current = Sku(
                    our_ref=code[:64],
                    our_barcode=barcode,
                    name=name,
                    design=design,
                    fabric=fabric,
                    supplier_ref=supplier_ref,
                    preferred_supplier_id=supplier.id if supplier else None,
                    reorder_min=minimum,
                    category=category,
                    stockist_ex_vat=prices.stockist_ex_vat,
                    wholesale_ex_vat=prices.wholesale_ex_vat,
                    decorator_ex_vat=prices.decorator_ex_vat,
                    retail_ex_vat=prices.retail_ex_vat,
                    carton_count=cartons,
                )
                self.session.add(current)
                existing[code] = current
                designs[(design.lower(), fabric.lower())] = code
                result.created += 1
                _note_price_changes(self.report, None, prices)
            else:
                same = (
                    current.name == name
                    and current.category == category
                    and current.supplier_ref == supplier_ref
                    and current.preferred_supplier_id == (supplier.id if supplier else None)
                    and current.reorder_min == minimum
                    and current.carton_count == cartons
                    and _dec_eq(current.stockist_ex_vat, prices.stockist_ex_vat)
                    and _dec_eq(current.wholesale_ex_vat, prices.wholesale_ex_vat)
                    and _dec_eq(current.decorator_ex_vat, prices.decorator_ex_vat)
                    and _dec_eq(current.retail_ex_vat, prices.retail_ex_vat)
                    and original_barcodes.get(code) == barcode
                )
                current.our_barcode = barcode
                if same:
                    result.unchanged += 1
                else:
                    _note_price_changes(self.report, current, prices)
                    current.name = name
                    current.category = category
                    current.supplier_ref = supplier_ref
                    current.preferred_supplier_id = supplier.id if supplier else None
                    current.reorder_min = minimum
                    current.carton_count = cartons
                    current.stockist_ex_vat = prices.stockist_ex_vat
                    current.wholesale_ex_vat = prices.wholesale_ex_vat
                    current.decorator_ex_vat = prices.decorator_ex_vat
                    current.retail_ex_vat = prices.retail_ex_vat
                    result.updated += 1
            self.skus[code] = current
        missing_code = len(rows) - len(by_code)
        if missing_code:
            result.skip("product row has no ProductCode", missing_code)
        await self.session.flush()

    async def _load_price_lists(self) -> None:
        lists = self._result("price_list")
        items = self._result("price_list_item")
        path = find_file(self.export_dir, "InventoryList", ".csv")
        if path is None:
            lists.skip("InventoryList file not found")
            items.skip("InventoryList file not found")
            return
        rows, _shifted = await self._read_csv(path)
        existing_lists = {
            row.name: row for row in (await self.session.scalars(select(PriceList))).all()
        }
        for tier in range(1, 11):
            positives = []
            for row in rows:
                code = row.get("ProductCode", "").strip()
                price = tier_amount_ex_vat(_tier_price(row, tier), tier)
                sku = self.skus.get(code)
                if price is None or sku is None:
                    continue
                positives.append((sku, price))
            if not positives:
                items.skip(f"PriceTier{tier} has no positive price")
                continue
            name = tier_price_list_name(tier)
            price_list = existing_lists.get(name)
            if price_list is None:
                price_list = PriceList(name=name)
                self.session.add(price_list)
                await self.session.flush()
                existing_lists[name] = price_list
                lists.created += 1
            else:
                lists.unchanged += 1
            current_items = {
                row.sku_id: row
                for row in (
                    await self.session.scalars(
                        select(PriceListItem).where(PriceListItem.price_list_id == price_list.id)
                    )
                ).all()
            }
            for sku, price in positives:
                current = current_items.get(sku.id)
                if current is None:
                    self.session.add(
                        PriceListItem(price_list_id=price_list.id, sku_id=sku.id, unit_ex_vat=price)
                    )
                    items.created += 1
                elif _dec_eq(current.unit_ex_vat, price):
                    items.unchanged += 1
                else:
                    current.unit_ex_vat = price
                    items.updated += 1
        await self.session.flush()

    async def _note_simple_prices(self) -> None:
        result = self._result("simple_prices")
        path = find_file(self.export_dir, "SimplePrices", ".csv")
        inventory = find_file(self.export_dir, "InventoryList", ".csv")
        if path is None:
            result.skip("SimplePrices file not found")
            return
        rows, _shifted = await self._read_csv(path)
        inventory_rows, _shifted = await self._read_csv(inventory) if inventory else ([], 0)
        by_code = {row.get("ProductCode", "").strip(): row for row in inventory_rows}
        mismatches = 0
        for row in rows:
            code = row.get("ProductCode", "").strip()
            source = by_code.get(code)
            if source is None:
                continue
            for tier in range(1, 11):
                if _tier_price(row, tier) != _tier_price(source, tier):
                    mismatches += 1
                    break
        result.skip(
            "price tiers are taken from InventoryList; SimplePrices is the same columns",
            len(rows),
        )
        if mismatches:
            result.note("SimplePrices tier differs from InventoryList for a product", mismatches)

    async def _note_markup_prices(self) -> None:
        result = self._result("markup_price")
        path = find_file(self.export_dir, "MarkupPrices", ".csv")
        if path is None:
            result.skip("MarkupPrices file not found")
            return
        rows, _shifted = await self._read_csv(path)
        nonzero = 0
        for row in rows:
            value = money(row.get("Value"), "0.000001")
            if value is not None and value != 0:
                nonzero += 1
        if nonzero == 0:
            result.skip("markup value is 0 on every row", len(rows))
        else:
            result.skip("markup rules have no price-list target", len(rows))

    async def _load_supplier_prices(self) -> None:
        result = self._result("sku_supplier_price")
        path = find_file(self.export_dir, "ProductPriceBySupplier", ".csv")
        if path is None:
            result.skip("ProductPriceBySupplier file not found")
            return
        rows, _shifted = await self._read_csv(path)
        existing = {
            (row.sku_id, row.supplier_id): row
            for row in (await self.session.scalars(select(SkuSupplierPrice))).all()
        }
        seen: set[tuple[uuid.UUID, uuid.UUID]] = set()
        for row in rows:
            sku = self.skus.get(row.get("SKU", "").strip())
            supplier = self.suppliers.get(_key(row.get("Supplier", "")))
            if sku is None or supplier is None:
                result.skip("supplier price SKU or supplier was not imported")
                continue
            key = (sku.id, supplier.id)
            if key in seen:
                result.skip("duplicate SKU and supplier price row")
                continue
            seen.add(key)
            latest = money(row.get("LatestPrice"), "0.0001")
            fixed = money(row.get("FixedPrice"), "0.0001")
            supplier_sku = clip(row.get("SupplierSKU"), 128)
            current = existing.get(key)
            if current is None:
                self.session.add(
                    SkuSupplierPrice(
                        sku_id=sku.id,
                        supplier_id=supplier.id,
                        supplier_sku=supplier_sku,
                        latest_price=latest,
                        fixed_price=fixed,
                    )
                )
                result.created += 1
            elif (
                current.supplier_sku == supplier_sku
                and _dec_eq(current.latest_price, latest)
                and _dec_eq(current.fixed_price, fixed)
            ):
                result.unchanged += 1
            else:
                current.supplier_sku = supplier_sku
                current.latest_price = latest
                current.fixed_price = fixed
                result.updated += 1
        await self.session.flush()

    async def _load_bom(self) -> None:
        result = self._result("sku_bom_line")
        path = find_file(self.export_dir, "AssemblyBOM", ".csv")
        if path is None:
            result.skip("AssemblyBOM file not found")
            return
        rows, _shifted = await self._read_csv(path)
        existing = {
            (row.parent_sku_id, row.component_sku_id): row
            for row in (await self.session.scalars(select(SkuBomLine))).all()
        }
        for row in rows:
            parent = self.skus.get(row.get("ProductSKU", "").strip())
            component = self.skus.get(row.get("ComponentSKU", "").strip())
            if parent is None or component is None:
                result.skip("BOM SKU was not imported")
                continue
            if parent.id == component.id:
                result.skip("BOM line names the parent as its own component")
                continue
            qty = money(row.get("Quantity"), "0.0001")
            if qty is None or qty <= 0:
                result.skip("BOM quantity is blank or not positive")
                continue
            key = (parent.id, component.id)
            current = existing.get(key)
            if current is None:
                current = SkuBomLine(
                    parent_sku_id=parent.id, component_sku_id=component.id, qty=qty
                )
                self.session.add(current)
                existing[key] = current
                result.created += 1
            elif _dec_eq(Decimal(current.qty), qty):
                result.unchanged += 1
            else:
                current.qty = qty
                result.updated += 1
        await self.session.flush()

    async def _load_stock(self) -> None:
        result = self._result("location_stock")
        path = find_file(self.export_dir, "StockOnHand", ".csv")
        if path is None:
            result.skip("StockOnHand file not found")
            return
        rows, _shifted = await self._read_csv(path)
        names = {_key(location.name): location.id for location in self.locations.values()}
        totals: dict[tuple[uuid.UUID, uuid.UUID], list[tuple[Decimal, Optional[Decimal]]]] = {}
        for row in rows:
            sku = self.skus.get(row.get("ProductCode", "").strip())
            if sku is None:
                result.skip("stock SKU was not imported")
                continue
            location_id = _match_location(row.get("Location", ""), row.get("Bin", ""), names)
            if location_id is None:
                result.skip("stock location did not match a location")
                continue
            qty_text = row.get("Quantity", "").strip()
            try:
                qty = Decimal(qty_text)
            except Exception:
                result.skip("stock quantity is not a number")
                continue
            if qty <= 0:
                result.skip("stock quantity is not positive")
                continue
            cost = money(row.get("AverageCost"), "0.0001")
            totals.setdefault((sku.id, location_id), []).append((qty, cost))
        existing = {
            (row.sku_id, row.location_id): row
            for row in (await self.session.scalars(select(LocationStock))).all()
        }
        floor_bins = {
            row.location_id: row
            for row in (
                await self.session.scalars(
                    select(LocationBin).where(LocationBin.is_default.is_(True))
                )
            ).all()
        }
        bin_rows = {
            (row.sku_id, row.bin_id): row
            for row in (await self.session.scalars(select(BinStock))).all()
        }
        for (sku_id, location_id), parts in totals.items():
            raw_qty = sum(qty for qty, _cost in parts)
            rounded = int(raw_qty.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
            if raw_qty != raw_qty.to_integral_value():
                result.note("on-hand rounded to an integer")
            if rounded <= 0:
                result.skip("rounded on-hand is 0")
                continue
            cost = _weighted_cost(parts)
            current = existing.get((sku_id, location_id))
            if current is None:
                current = LocationStock(
                    sku_id=sku_id,
                    location_id=location_id,
                    on_hand=rounded,
                    unit_cost_zar=cost,
                )
                self.session.add(current)
                existing[(sku_id, location_id)] = current
                result.created += 1
            elif current.on_hand == rounded and _dec_eq(current.unit_cost_zar, cost):
                result.unchanged += 1
            else:
                current.on_hand = rounded
                current.unit_cost_zar = cost
                result.updated += 1
            floor = floor_bins.get(location_id)
            if floor is None:
                continue
            bin_row = bin_rows.get((sku_id, floor.id))
            if bin_row is None:
                self.session.add(BinStock(sku_id=sku_id, bin_id=floor.id, on_hand=rounded))
            else:
                bin_row.on_hand = rounded
        await self.session.flush()

    async def _load_sales_orders(self) -> None:
        orders = self._result("sales_order")
        lines = self._result("sales_order_line")
        path = find_file(self.export_dir, "Sale_Order_Details", ".xlsx")
        if path is None:
            orders.skip("Sale_Order_Details file not found")
            lines.skip("Sale_Order_Details file not found")
            return
        records, filled = await self._read_xlsx(path)
        self.report.filled_down["Sale_Order_Details"] = filled
        existing = {
            row.so_number: row
            for row in (
                await self.session.scalars(
                    select(SalesOrder).options(selectinload(SalesOrder.lines))
                )
            ).all()
        }
        for number, group in _group(records, "Order #"):
            if not number:
                orders.skip("sales order has no order number")
                continue
            if len(number) > 64:
                orders.skip("sales order number is too long")
                continue
            status_text = group[0].get("Status", "").strip().lower()
            status = SO_STATUS.get(status_text)
            if status is None:
                orders.skip(f"sales order status {status_text or '(blank)'} is not mapped")
                lines.skip("sales order was skipped", len(group))
                continue
            customer = await self._ensure_customer(group[0].get("Customer", ""))
            if customer is None:
                orders.skip("sales order has no customer")
                lines.skip("sales order was skipped", len(group))
                continue
            built = _sales_lines(group, self.skus, lines)
            if not built:
                orders.skip("sales order has no importable lines")
                continue
            issue = parse_date(group[0].get("Order date"))
            notes = f"Cin7 archive. Status: {group[0].get('Status', '').strip()}"
            if issue is not None:
                notes = f"{notes} Date: {issue.isoformat()}"
            current = existing.get(number)
            signature = [(line["sku_id"], line["qty"], line["description"]) for line in built]
            if current is None:
                current = SalesOrder(
                    so_number=number,
                    customer_id=customer.id,
                    hold_stock=False,
                    awaiting_stock=False,
                    status=status,
                    subtotal_ex_vat=ZERO,
                    vat_amount=ZERO,
                    total_inc_vat=ZERO,
                    amount_paid=ZERO,
                    notes=notes,
                    prices_include_vat=shows_prices_including_vat(customer),
                    is_archive=True,
                )
                self.session.add(current)
                await self.session.flush()
                existing[number] = current
                orders.created += 1
                await self._replace_sales_lines(current, built)
            elif _sales_same(current, customer.id, status, notes, signature):
                orders.unchanged += 1
                lines.unchanged += len(built)
            else:
                current.customer_id = customer.id
                current.status = status
                current.notes = notes
                current.hold_stock = False
                current.awaiting_stock = False
                current.is_archive = True
                current.subtotal_ex_vat = ZERO
                current.vat_amount = ZERO
                current.total_inc_vat = ZERO
                current.amount_paid = ZERO
                await self._replace_sales_lines(current, built)
                orders.updated += 1
        await self.session.flush()

    async def _replace_sales_lines(self, order: SalesOrder, built: list[dict[str, object]]) -> None:
        await self.session.execute(
            delete(SalesOrderLine).where(SalesOrderLine.sales_order_id == order.id)
        )
        for line in built:
            self.session.add(
                SalesOrderLine(
                    sales_order_id=order.id,
                    sku_id=line["sku_id"],
                    qty=line["qty"],
                    unit_ex_vat=ZERO,
                    description=str(line["description"]),
                    held_qty=0,
                )
            )
        self._result("sales_order_line").created += len(built)

    async def _load_invoices(self) -> None:
        invoices = self._result("tax_invoice")
        lines = self._result("invoice_line")
        credits = self._result("archive_credit_note")
        path = find_file(self.export_dir, "Sale_Documents", ".xlsx")
        if path is None:
            invoices.skip("Sale_Documents file not found")
            lines.skip("Sale_Documents file not found")
            credits.skip("Sale_Documents file not found")
            return
        records, filled = await self._read_xlsx(path)
        self.report.filled_down["Sale_Documents"] = filled
        invoice_rows: list[dict[str, str]] = []
        for row in records:
            number = row.get("Document #", "").strip()
            if number.upper().startswith("CR"):
                self._credit_rows.append(row)
                continue
            invoice_rows.append(row)
        existing = {
            row.invoice_number: row
            for row in (
                await self.session.scalars(
                    select(TaxInvoice).options(selectinload(TaxInvoice.lines))
                )
            ).all()
        }
        for number, group in _group(invoice_rows, "Document #"):
            if not number:
                invoices.skip("invoice has no document number")
                continue
            if len(number) > 32:
                invoices.skip("invoice number is longer than 32 characters")
                lines.skip("invoice was skipped", len(group))
                continue
            customer = await self._ensure_customer(group[0].get("Customer", ""))
            issue = parse_date(group[0].get("Date"))
            if customer is None or issue is None:
                invoices.skip("invoice is missing a customer or a date")
                lines.skip("invoice was skipped", len(group))
                continue
            built = _invoice_lines(group, self.skus, lines)
            if not built:
                invoices.skip("invoice has no importable lines")
                continue
            subtotal = sum((line["ex_vat"] for line in built), ZERO)
            vat = sum((line["vat_amount"] for line in built), ZERO)
            total = sum((line["inc_vat"] for line in built), ZERO)
            current = existing.get(number)
            signature = _invoice_signature(built)
            if current is None:
                current = TaxInvoice(
                    invoice_number=number,
                    customer_id=customer.id,
                    issue_date=issue,
                    subtotal_ex_vat=subtotal,
                    vat_amount=vat,
                    total_inc_vat=total,
                    amount_paid=ZERO,
                    prices_include_vat=shows_prices_including_vat(customer),
                    is_archive=True,
                )
                self.session.add(current)
                await self.session.flush()
                existing[number] = current
                invoices.created += 1
                await self._replace_invoice_lines(current, built)
            elif _invoice_same(current, customer.id, issue, subtotal, vat, total, signature):
                invoices.unchanged += 1
                lines.unchanged += len(built)
            else:
                current.customer_id = customer.id
                current.issue_date = issue
                current.subtotal_ex_vat = subtotal
                current.vat_amount = vat
                current.total_inc_vat = total
                current.amount_paid = ZERO
                current.is_archive = True
                await self._replace_invoice_lines(current, built)
                invoices.updated += 1
        await self.session.flush()

    async def _load_archive_credit_notes(self) -> None:
        """Store Cin7 ``CR-*`` documents as archive credit notes. No journal, no stock."""
        notes = self._result("archive_credit_note")
        lines = self._result("archive_credit_note_line")
        if not self._credit_rows:
            return
        existing = {
            row.document_number: row
            for row in (
                await self.session.scalars(
                    select(ArchiveCreditNote).options(selectinload(ArchiveCreditNote.lines))
                )
            ).all()
        }
        for number, group in _group(self._credit_rows, "Document #"):
            if len(number) > 64:
                notes.skip("credit note number is longer than 64 characters")
                lines.skip("credit note was skipped", len(group))
                continue
            issue = parse_date(group[0].get("Date"))
            if issue is None:
                notes.skip("credit note has no date")
                lines.skip("credit note was skipped", len(group))
                continue
            customer = await self._ensure_customer(group[0].get("Customer", ""))
            built = _credit_lines(group, self.skus, lines)
            if not built:
                notes.skip("credit note has no lines")
                continue
            subtotal = sum((line["ex_vat"] for line in built), ZERO)
            vat = sum((line["vat_amount"] for line in built), ZERO)
            total = sum((line["inc_vat"] for line in built), ZERO)
            signature = [tuple(str(line[k]) for k in sorted(line)) for line in built]
            customer_id = customer.id if customer else None
            current = existing.get(number)
            if current is not None:
                current_sig = [
                    tuple(
                        str(v)
                        for _k, v in sorted(
                            {
                                "description": line.description,
                                "ex_vat": line.ex_vat,
                                "inc_vat": line.inc_vat,
                                "qty": line.qty,
                                "sku_code": line.sku_code,
                                "sku_id": line.sku_id,
                                "vat_amount": line.vat_amount,
                            }.items()
                        )
                    )
                    for line in current.lines
                ]
                if (
                    current.customer_id == customer_id
                    and current.issue_date == issue
                    and current_sig == signature
                ):
                    notes.unchanged += 1
                    lines.unchanged += len(built)
                    continue
                current.customer_id = customer_id
                current.issue_date = issue
                current.subtotal_ex_vat = subtotal
                current.vat_amount = vat
                current.total_inc_vat = total
                await self.session.execute(
                    delete(ArchiveCreditNoteLine).where(
                        ArchiveCreditNoteLine.credit_note_id == current.id
                    )
                )
                notes.updated += 1
            else:
                current = ArchiveCreditNote(
                    document_number=number,
                    customer_id=customer_id,
                    issue_date=issue,
                    subtotal_ex_vat=subtotal,
                    vat_amount=vat,
                    total_inc_vat=total,
                    source="cin7",
                )
                self.session.add(current)
                await self.session.flush()
                existing[number] = current
                notes.created += 1
            for index, line in enumerate(built):
                self.session.add(
                    ArchiveCreditNoteLine(credit_note_id=current.id, sort_order=index, **line)
                )
                lines.created += 1
        await self.session.flush()

    async def _replace_invoice_lines(
        self, invoice: TaxInvoice, built: list[dict[str, object]]
    ) -> None:
        await self.session.execute(delete(InvoiceLine).where(InvoiceLine.invoice_id == invoice.id))
        for index, line in enumerate(built):
            self.session.add(
                InvoiceLine(
                    invoice_id=invoice.id,
                    description=str(line["description"])[:512],
                    qty=int(line["qty"]),
                    unit_ex_vat=line["unit_ex_vat"],
                    ex_vat=line["ex_vat"],
                    inc_vat=line["inc_vat"],
                    vat_amount=line["vat_amount"],
                    sort_order=index,
                    sku_id=line["sku_id"],
                )
            )
        self._result("invoice_line").created += len(built)

    async def _link_orders_to_invoices(self) -> None:
        path = find_file(self.export_dir, "Sales_by_Product", ".xlsx")
        orders = self._result("sales_order")
        if path is None:
            return
        records, filled = await self._read_xlsx(path)
        self.report.filled_down["Sales_by_Product"] = filled
        links: dict[str, set[str]] = {}
        for row in records:
            order_number = row.get("Order #", "").strip()
            document = row.get("Document #", "").strip()
            if order_number and document.upper().startswith("INV"):
                links.setdefault(order_number, set()).add(document)
        if not links:
            return
        existing_orders = {
            row.so_number: row for row in (await self.session.scalars(select(SalesOrder))).all()
        }
        existing_invoices = {
            row.invoice_number: row.id
            for row in (await self.session.scalars(select(TaxInvoice))).all()
        }
        for order_number, documents in links.items():
            order = existing_orders.get(order_number)
            if order is None or not order.is_archive:
                continue
            invoice_ids = [
                existing_invoices[number]
                for number in sorted(documents)
                if number in existing_invoices
            ]
            if len(invoice_ids) != 1:
                if len(documents) > 1:
                    orders.note("sales order has more than one invoice and was not linked")
                continue
            if order.invoice_id != invoice_ids[0]:
                order.invoice_id = invoice_ids[0]
                if order.status != SalesOrderStatus.INVOICED:
                    orders.note("linked an archive sales order to its invoice")
        await self.session.flush()

    async def _load_purchase_orders(self) -> None:
        orders = self._result("purchase_order")
        lines = self._result("po_line")
        path = find_file(self.export_dir, "Purchase_Order_Details", ".xlsx")
        if path is None:
            orders.skip("Purchase_Order_Details file not found")
            lines.skip("Purchase_Order_Details file not found")
            return
        records, filled = await self._read_xlsx(path)
        self.report.filled_down["Purchase_Order_Details"] = filled
        existing = {
            row.po_number: row
            for row in (
                await self.session.scalars(
                    select(PurchaseOrder).options(selectinload(PurchaseOrder.lines))
                )
            ).all()
        }
        for number, group in _group(records, "PO #"):
            if not number:
                orders.skip("purchase order has no PO number")
                continue
            if len(number) > 32:
                orders.skip("purchase order number is longer than 32 characters")
                continue
            status_text = group[0].get("Status", "").strip().lower()
            status = PO_STATUS.get(status_text)
            if status is None:
                orders.skip(f"purchase order status {status_text or '(blank)'} is not mapped")
                lines.skip("purchase order was skipped", len(group))
                continue
            supplier = await self._ensure_supplier(group[0].get("Supplier", ""))
            if supplier is None:
                orders.skip("purchase order has no supplier")
                lines.skip("purchase order was skipped", len(group))
                continue
            built = _po_lines(group, self.skus, lines)
            if not built:
                orders.skip("purchase order has no importable lines")
                continue
            ordered = parse_date(group[0].get("PO date"))
            received = parse_date(group[0].get("Invoice date")) or ordered
            ordered_at = _utc(ordered) if ordered else None
            received_at = (
                _utc(received) if status == PurchaseOrderStatus.RECEIVED and received else None
            )
            current = existing.get(number)
            signature = [(line["sku_id"], line["qty"], str(line["cost"])) for line in built]
            if current is None:
                current = PurchaseOrder(
                    po_number=number,
                    supplier_id=supplier.id,
                    status=status,
                    ordered_at=ordered_at,
                    received_at=received_at,
                    is_archive=True,
                )
                self.session.add(current)
                await self.session.flush()
                existing[number] = current
                orders.created += 1
                await self._replace_po_lines(current, built)
            elif _po_same(current, supplier.id, status, ordered_at, received_at, signature):
                orders.unchanged += 1
                lines.unchanged += len(built)
            else:
                current.supplier_id = supplier.id
                current.status = status
                current.ordered_at = ordered_at
                current.received_at = received_at
                current.is_archive = True
                current.received_location_id = None
                await self._replace_po_lines(current, built)
                orders.updated += 1
        await self.session.flush()

    async def _replace_po_lines(self, order: PurchaseOrder, built: list[dict[str, object]]) -> None:
        await self.session.execute(delete(PoLine).where(PoLine.po_id == order.id))
        for line in built:
            self.session.add(
                PoLine(
                    po_id=order.id,
                    sku_id=line["sku_id"],
                    qty=int(line["qty"]),
                    factory_unit_amount=line["cost"],
                )
            )
        self._result("po_line").created += len(built)

    async def _load_bills(self) -> None:
        bills = self._result("bill")
        lines = self._result("bill_line")
        path = find_file(self.export_dir, "Purchase_Invoice_Details", ".xlsx")
        if path is None:
            bills.skip("Purchase_Invoice_Details file not found")
            lines.skip("Purchase_Invoice_Details file not found")
            return
        records, filled = await self._read_xlsx(path)
        self.report.filled_down["Purchase_Invoice_Details"] = filled
        existing = {
            row.bill_number: row
            for row in (
                await self.session.scalars(select(Bill).options(selectinload(Bill.lines)))
            ).all()
        }
        for number, group in _group(records, "Invoice #"):
            if not number:
                bills.skip("bill has no invoice number")
                continue
            if len(number) > 128:
                bills.skip("bill number is longer than 128 characters")
                lines.skip("bill was skipped", len(group))
                continue
            supplier = await self._ensure_supplier(group[0].get("Supplier", ""))
            issue = parse_date(group[0].get("Invoice date"))
            if supplier is None or issue is None:
                bills.skip("bill is missing a supplier or a date")
                lines.skip("bill was skipped", len(group))
                continue
            built = _bill_lines(group, lines)
            if not built:
                bills.skip("bill has no importable lines")
                continue
            currency = self.supplier_currency.get(_key(supplier.name), supplier.default_currency)
            foreign = sum((line["amount"] for line in built), ZERO)
            if currency == "ZAR":
                fx = FX_ONE
                amount_zar = foreign
            else:
                fx = FX_ZERO
                amount_zar = ZERO
                bills.note(
                    "non-ZAR bill: currency and foreign amount kept, ZAR unknown (fx_rate_known false)"
                )
            fx_known = currency == "ZAR"
            current = existing.get(number)
            signature = [(line["description"], line["qty"], str(line["amount"])) for line in built]
            if current is None:
                current = Bill(
                    bill_number=number,
                    supplier_id=supplier.id,
                    supplier_ref=number[:128],
                    issue_date=issue,
                    currency=currency,
                    fx_to_zar=fx,
                    amount_foreign=foreign,
                    amount_zar=amount_zar,
                    amount_paid_zar=ZERO,
                    is_archive=True,
                    fx_rate_known=fx_known,
                )
                self.session.add(current)
                await self.session.flush()
                existing[number] = current
                bills.created += 1
                await self._replace_bill_lines(current, built)
            elif current.fx_rate_known == fx_known and _bill_same(
                current, supplier.id, issue, currency, fx, foreign, amount_zar, signature
            ):
                bills.unchanged += 1
                lines.unchanged += len(built)
            else:
                current.supplier_id = supplier.id
                current.supplier_ref = number[:128]
                current.issue_date = issue
                current.currency = currency
                current.fx_to_zar = fx
                current.amount_foreign = foreign
                current.amount_zar = amount_zar
                current.fx_rate_known = fx_known
                current.amount_paid_zar = ZERO
                current.is_archive = True
                await self._replace_bill_lines(current, built)
                bills.updated += 1
        await self.session.flush()

    async def _replace_bill_lines(self, bill: Bill, built: list[dict[str, object]]) -> None:
        await self.session.execute(delete(BillLine).where(BillLine.bill_id == bill.id))
        for index, line in enumerate(built):
            self.session.add(
                BillLine(
                    bill_id=bill.id,
                    description=str(line["description"])[:512],
                    qty=int(line["qty"]),
                    unit_amount=line["unit"],
                    amount_foreign=line["amount"],
                    sort_order=index,
                )
            )
        self._result("bill_line").created += len(built)

    async def _note_unused_files(self) -> None:
        availability = find_file(self.export_dir, "AvailabilityReport", ".csv")
        if availability is not None:
            rows, _shifted = await self._read_csv(availability)
            self._result("availability").skip(
                "availability is a derived stock view; on-hand comes from StockOnHand",
                len(rows),
            )
        else:
            self._result("availability").skip("AvailabilityReport file not found")
        smart = find_file(self.export_dir, "SmartReordering", ".csv")
        if smart is not None:
            rows, _shifted = await self._read_csv(smart)
            self._result("smart_reorder").skip(
                "reorder_min is taken from the product MinimumBeforeReorder; "
                "per-supplier lead settings were not stored",
                len(rows),
            )
        else:
            self._result("smart_reorder").skip("SmartReordering file not found")
        reorder_locations = find_file(self.export_dir, "StockReorder", ".csv")
        if reorder_locations is not None:
            rows, _shifted = await self._read_csv(reorder_locations)
            self._result("stock_reorder_location").skip(
                "reorder minimums are per SKU, not per location",
                len(rows),
            )
        else:
            self._result("stock_reorder_location").skip("StockReorder file not found")


def _collapse(
    rows: list[dict[str, str]],
    name_column: str,
    default_column: str,
) -> tuple[list[dict[str, str]], int]:
    grouped: dict[str, list[dict[str, str]]] = {}
    order: list[str] = []
    for row in rows:
        name = row.get(name_column, "").strip()
        if not name:
            continue
        key = _key(name)
        if key not in grouped:
            grouped[key] = []
            order.append(key)
        grouped[key].append(row)
    chosen: list[dict[str, str]] = []
    folded = 0
    for key in order:
        group = grouped[key]
        chosen.append(_pick_contact_row(group, default_column))
        folded += len(group) - 1
    return chosen, folded


def _customer_same(current: Customer, payload: dict[str, object]) -> bool:
    return (
        current.email == payload["email"]
        and current.phone == payload["phone"]
        and current.vat_number == payload["vat_number"]
        and current.customer_type == payload["customer_type"]
        and current.price_classification == payload["price_classification"]
        and current.price_tier == payload["price_tier"]
        and _dec_eq(current.credit_limit, payload["credit_limit"])  # type: ignore[arg-type]
        and current.on_hold == payload["on_hold"]
        and current.payment_terms_days == payload["payment_terms_days"]
    )


def _tier_price(row: dict[str, str], tier: int) -> Optional[Decimal]:
    return money(row.get(f"PriceTier{tier}"))


def _weighted_cost(parts: list[tuple[Decimal, Optional[Decimal]]]) -> Optional[Decimal]:
    weighted = [(qty, cost) for qty, cost in parts if cost is not None and qty > 0]
    total_qty = sum(qty for qty, _cost in weighted)
    if total_qty <= 0:
        return None
    amount = sum(qty * cost for qty, cost in weighted)
    return (amount / total_qty).quantize(Decimal("0.0001"))


def _sales_lines(
    group: list[dict[str, str]],
    skus: dict[str, Sku],
    result: EntityResult,
) -> list[dict[str, object]]:
    built: list[dict[str, object]] = []
    for row in group:
        sku = skus.get(row.get("SKU", "").strip())
        if sku is None:
            result.skip("sales order SKU was not imported")
            continue
        qty, reason = integral_qty(row.get("Quantity Total"))
        if qty is None:
            result.skip(f"sales order {reason}")
            continue
        description = clip(row.get("Product"), 512) or sku.name
        built.append({"sku_id": sku.id, "qty": qty, "description": description})
    merged: dict[uuid.UUID, dict[str, object]] = {}
    for line in built:
        current = merged.get(line["sku_id"])  # type: ignore[arg-type]
        if current is None:
            merged[line["sku_id"]] = line  # type: ignore[index]
        else:
            current["qty"] = int(current["qty"]) + int(line["qty"])
    return list(merged.values())


def _sales_same(
    current: SalesOrder,
    customer_id: uuid.UUID,
    status: SalesOrderStatus,
    notes: str,
    signature: list[tuple[object, object, object]],
) -> bool:
    if not current.is_archive or current.customer_id != customer_id or current.status != status:
        return False
    if (current.notes or "") != notes:
        return False
    existing = sorted((line.sku_id, line.qty, line.description) for line in current.lines)
    return existing == sorted(signature)  # type: ignore[arg-type]


def _invoice_lines(
    group: list[dict[str, str]],
    skus: dict[str, Sku],
    result: EntityResult,
) -> list[dict[str, object]]:
    built: list[dict[str, object]] = []
    for row in group:
        qty, reason = integral_qty(row.get("Quantity"))
        if qty is None:
            result.skip(f"invoice {reason}")
            continue
        code = row.get("SKU", "").strip()
        sku = skus.get(code) if code else None
        if code and sku is None:
            result.skip("invoice SKU was not imported")
            continue
        ex_vat = money(row.get("Amount")) or ZERO
        vat_amount = money(row.get("Tax")) or ZERO
        inc_vat = money(row.get("Total"))
        if inc_vat is None:
            inc_vat = (ex_vat + vat_amount).quantize(Decimal("0.01"))
        unit = (ex_vat / Decimal(qty)).quantize(Decimal("0.01"))
        description = clip(row.get("Product"), 512) or (sku.name if sku else "Cin7 line")
        built.append(
            {
                "sku_id": sku.id if sku else None,
                "qty": qty,
                "description": description,
                "unit_ex_vat": unit,
                "ex_vat": ex_vat,
                "vat_amount": vat_amount,
                "inc_vat": inc_vat,
            }
        )
    return built


def _credit_lines(
    group: list[dict[str, str]],
    skus: dict[str, Sku],
    result: EntityResult,
) -> list[dict[str, object]]:
    """Credit lines keep Cin7's sign (negative) and fractional quantities as exported."""
    built: list[dict[str, object]] = []
    for row in group:
        qty = money(row.get("Quantity"), "0.0001")
        if qty is None or qty == 0:
            result.skip("credit note line has no quantity")
            continue
        code = clip(row.get("SKU"), 128)
        sku = skus.get(code) if code else None
        ex_vat = money(row.get("Amount")) or ZERO
        vat_amount = money(row.get("Tax")) or ZERO
        inc_vat = money(row.get("Total"))
        if inc_vat is None:
            inc_vat = (ex_vat + vat_amount).quantize(Decimal("0.01"))
        built.append(
            {
                "sku_id": sku.id if sku else None,
                "sku_code": code,
                "description": clip(row.get("Product"), 4000)
                or (sku.name if sku else "Cin7 credit"),
                "qty": qty,
                "ex_vat": ex_vat,
                "vat_amount": vat_amount,
                "inc_vat": inc_vat,
            }
        )
    return built


def _invoice_signature(built: list[dict[str, object]]) -> list[tuple[object, ...]]:
    return [
        (
            line["sku_id"],
            line["qty"],
            line["description"],
            str(line["ex_vat"]),
            str(line["vat_amount"]),
            str(line["inc_vat"]),
        )
        for line in built
    ]


def _invoice_same(
    current: TaxInvoice,
    customer_id: uuid.UUID,
    issue: datetime.date,
    subtotal: Decimal,
    vat: Decimal,
    total: Decimal,
    signature: list[tuple[object, ...]],
) -> bool:
    if (
        not current.is_archive
        or current.customer_id != customer_id
        or current.issue_date != issue
        or not _dec_eq(current.subtotal_ex_vat, subtotal)
        or not _dec_eq(current.vat_amount, vat)
        or not _dec_eq(current.total_inc_vat, total)
    ):
        return False
    existing = [
        (
            line.sku_id,
            line.qty,
            line.description,
            str(line.ex_vat),
            str(line.vat_amount),
            str(line.inc_vat),
        )
        for line in current.lines
    ]
    return existing == signature


def _po_lines(
    group: list[dict[str, str]],
    skus: dict[str, Sku],
    result: EntityResult,
) -> list[dict[str, object]]:
    merged: dict[uuid.UUID, dict[str, object]] = {}
    for row in group:
        sku = skus.get(row.get("SKU", "").strip())
        if sku is None:
            result.skip("purchase order SKU was not imported")
            continue
        qty, reason = integral_qty(row.get("Quantity"))
        if qty is None:
            result.skip(f"purchase order {reason}")
            continue
        cost = money(row.get("Cost"), "0.0001")
        if cost is None or cost <= 0:
            result.skip("purchase order factory unit amount must be greater than 0")
            continue
        current = merged.get(sku.id)
        if current is None:
            merged[sku.id] = {"sku_id": sku.id, "qty": qty, "cost": cost, "weight": Decimal(qty)}
        else:
            total_qty = int(current["qty"]) + qty
            weighted = (Decimal(current["cost"]) * Decimal(current["weight"])) + (
                cost * Decimal(qty)
            )
            current["qty"] = total_qty
            current["weight"] = Decimal(total_qty)
            current["cost"] = (weighted / Decimal(total_qty)).quantize(Decimal("0.0001"))
    return list(merged.values())


def _po_same(
    current: PurchaseOrder,
    supplier_id: uuid.UUID,
    status: PurchaseOrderStatus,
    ordered_at: Optional[datetime.datetime],
    received_at: Optional[datetime.datetime],
    signature: list[tuple[object, object, str]],
) -> bool:
    if (
        not current.is_archive
        or current.supplier_id != supplier_id
        or current.status != status
        or current.ordered_at != ordered_at
        or current.received_at != received_at
    ):
        return False
    existing = sorted(
        (line.sku_id, line.qty, str(line.factory_unit_amount)) for line in current.lines
    )
    return existing == sorted(signature)


def _bill_lines(group: list[dict[str, str]], result: EntityResult) -> list[dict[str, object]]:
    built: list[dict[str, object]] = []
    for row in group:
        qty, reason = integral_qty(row.get("Quantity"))
        if qty is None:
            result.skip(f"bill {reason}")
            continue
        unit = money(row.get("Price")) or ZERO
        amount = money(row.get("Total"))
        if amount is None:
            amount = (unit * Decimal(qty)).quantize(Decimal("0.01"))
        description = clip(row.get("Product"), 512) or clip(row.get("SKU"), 512) or "Cin7 line"
        built.append({"description": description, "qty": qty, "unit": unit, "amount": amount})
    return built


def _bill_same(
    current: Bill,
    supplier_id: uuid.UUID,
    issue: datetime.date,
    currency: str,
    fx: Decimal,
    foreign: Decimal,
    amount_zar: Decimal,
    signature: list[tuple[object, object, str]],
) -> bool:
    if (
        not current.is_archive
        or current.supplier_id != supplier_id
        or current.issue_date != issue
        or current.currency != currency
        or not _dec_eq(current.fx_to_zar, fx)
        or not _dec_eq(current.amount_foreign, foreign)
        or not _dec_eq(current.amount_zar, amount_zar)
    ):
        return False
    existing = [(line.description, line.qty, str(line.amount_foreign)) for line in current.lines]
    return existing == signature


async def run_import(session: AsyncSession, export_dir: Path) -> ImportReport:
    """Upsert a Cin7 Core export. The caller commits or rolls back."""
    loader = Cin7Loader(session, export_dir)
    return await loader.run()
