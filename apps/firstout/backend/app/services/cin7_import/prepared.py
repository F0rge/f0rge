"""Strict prepared-package adapter. The caller owns the complete transaction."""

from __future__ import annotations

import csv
import datetime
import hashlib
import io
import json
import tempfile
import uuid
from collections import defaultdict
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation, localcontext
from pathlib import Path
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.archive_credit_note import ArchiveCreditNote, ArchiveCreditNoteLine
from app.models.bill import Bill, BillLine
from app.models.customer import Customer
from app.models.inventory import LocationStock
from app.models.location import Location
from app.models.location_bin import BinStock, LocationBin
from app.models.purchase_order import PoLine, PurchaseOrder
from app.models.sales_order import SalesOrder, SalesOrderLine
from app.models.sku import Sku
from app.models.supplier import Supplier
from app.models.price_list import PriceList, PriceListItem
from app.models.tax_invoice import InvoiceLine, TaxInvoice
from app.services.cin7_import.load import PO_STATUS, SO_STATUS, run_import
from app.services.cin7_import.parse import parse_date, tier_price_list_name
from app.services.pricing import shows_prices_including_vat
from app.services.quantities import exact_quantity
from app.services.suppliers import normalize_vat_number
from f0rge_core.exceptions import ValidationError
from f0rge_db.organisation import tenant_id_ctx

CENT = Decimal("0.01")
ZERO = Decimal(0)
MASTER_FILES = (
    "data/Customers_cleaned.csv",
    "data/CustomerContacts_cleaned.csv",
    "data/CustomerAddresses_cleaned.csv",
    "data/Suppliers_cleaned.csv",
    "data/SupplierContacts_cleaned.csv",
    "data/SupplierAddresses_cleaned.csv",
    "data/InventoryList_cleaned.csv",
    "data/AssemblyBOM_cleaned.csv",
    "data/ProductPriceBySupplier_cleaned.csv",
)
HISTORY_FILES = (
    "history/SaleInvoicesCreditNotes.csv",
    "history/SaleOrderDetails.csv",
    "history/PurchaseInvoicesCreditNotes.csv",
    "history/PurchaseOrderDetails.csv",
)
CANDIDATE_FILES = frozenset((*MASTER_FILES, "data/StockOnHand_cleaned.csv", *HISTORY_FILES))
EVIDENCE_FILES = frozenset(
    (
        "audit/party-archive-state.csv",
        "audit/held-orphan-contacts.csv",
        "reference/source-locations-and-bins.csv",
    )
)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _key(value: str) -> str:
    return value.strip().lower()


def _required(row: dict[str, str], name: str, limit: Optional[int] = None) -> str:
    value = row.get(name, "")
    if not value.strip() or (limit is not None and len(value) > limit):
        raise ValidationError(f"Prepared source requires a valid {name} within its field limit")
    return value


def _amount(value: str, *, places: int = 2, nullable: bool = False) -> Optional[Decimal]:
    if not value.strip() and nullable:
        return None
    try:
        amount = Decimal(value)
        quantum = Decimal(1).scaleb(-places)
        if not amount.is_finite() or amount != amount.quantize(quantum):
            raise ValueError
        return amount
    except (InvalidOperation, ValueError) as exc:
        raise ValidationError(
            "Prepared amount is missing, nonfinite or exceeds source precision"
        ) from exc


def _source_cost(value: str) -> Optional[Decimal]:
    """Retain every source decimal digit until the stored weighted-cost boundary."""
    if not value.strip():
        return None
    try:
        cost = Decimal(value)
        if not cost.is_finite():
            raise ValueError
        return cost if cost > 0 else None
    except (InvalidOperation, ValueError) as exc:
        raise ValidationError("Prepared stock cost must be a finite source decimal") from exc


def _day(value: str) -> datetime.date:
    day = parse_date(value)
    if day is None:
        raise ValidationError("Prepared document has an invalid date")
    return day


def _whole(value: str) -> int:
    quantity = exact_quantity(value)
    if quantity <= 0 or quantity != quantity.to_integral_value():
        raise ValidationError("Prepared sales lines require positive whole quantities")
    return int(quantity)


def _archived(value: str) -> bool:
    if value.strip().lower() not in {"true", "false"}:
        raise ValidationError("Prepared party archive flag must be explicit true or false")
    return value.strip().lower() == "true"


@dataclass(frozen=True)
class PreparedPackage:
    root: Path
    manifest: dict
    manifest_sha256: str
    rows: dict[str, list[dict[str, str]]]
    verified_bytes: dict[str, bytes]

    @classmethod
    def read(cls, root: Path, expected_manifest_sha256: str) -> "PreparedPackage":
        root = root.resolve(strict=True)
        manifest_path = root / "StageManifest.json"
        manifest_raw = manifest_path.read_bytes()
        digest = hashlib.sha256(manifest_raw).hexdigest()
        if digest != expected_manifest_sha256:
            raise ValidationError("Prepared manifest hash does not match the reviewed package")
        manifest = json.loads(manifest_raw)
        if (
            manifest.get("schema_version") != 1
            or manifest.get("package_kind") != "firstout_primavera_filtered_operational_staging"
        ):
            raise ValidationError("Unsupported prepared package format")
        candidates = manifest.get("import_candidate_files", {})
        evidence = manifest.get("evidence_files_never_import", {})
        if set(candidates) != CANDIDATE_FILES or set(evidence) != EVIDENCE_FILES:
            raise ValidationError(
                "Prepared manifest does not match the exact reviewed file allowlist"
            )
        rows = {}
        verified_bytes = {}
        for relative, spec in {**candidates, **evidence}.items():
            path = root / relative
            if path.is_symlink() or not path.resolve(strict=True).is_relative_to(root):
                raise ValidationError("Prepared package file escapes its reviewed directory")
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != spec.get("sha256"):
                raise ValidationError(f"Prepared file hash changed: {relative}")
            values = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline="")))
            if len(values) != spec.get("rows") or any(
                None in row or None in row.values() for row in values
            ):
                raise ValidationError(f"Prepared file row shape/count changed: {relative}")
            if relative in CANDIDATE_FILES:
                rows[relative] = values
                verified_bytes[relative] = raw
        package = cls(root, manifest, digest, rows, verified_bytes)
        package.validate_source()
        return package

    def validate_source(self) -> None:
        for file, count_key in (("Customers", "Customers"), ("Suppliers", "Suppliers")):
            rows = self.rows[f"data/{file}_cleaned.csv"]
            keys = [_key(_required(row, "Name", 255)) for row in rows]
            spec = self.manifest["counts"][count_key]
            if len(keys) != len(set(keys)) or len(keys) != spec["total"]:
                raise ValidationError("Prepared party identities are not unique and complete")
            archived = sum(_archived(_required(row, "is_archived")) for row in rows)
            if archived != spec["archived"] or len(rows) - archived != spec["active"]:
                raise ValidationError(
                    "Prepared active/archive partition differs from reviewed counts"
                )
        sku_rows = self.rows["data/InventoryList_cleaned.csv"]
        codes = [_required(row, "ProductCode", 64) for row in sku_rows]
        barcodes = [_required(row, "Barcode", 64) for row in sku_rows]
        if (
            len(codes) != len(set(codes))
            or len(barcodes) != len(set(barcodes))
            or "AU0001" in codes
        ):
            raise ValidationError(
                "Prepared product identities/barcodes are not unique or contain AU0001"
            )
        if len(codes) != self.manifest["counts"]["products"]:
            raise ValidationError("Prepared product count differs from reviewed counts")
        known = set(codes)
        for row in sku_rows:
            if row.get("Sellable", "").strip().lower() not in {"yes", "no"}:
                raise ValidationError("Prepared product Sellable must be explicit Yes or No")
        if (
            sum(row["Sellable"].strip().lower() == "no" for row in sku_rows)
            != self.manifest["counts"]["nonsellable_source_products"]
        ):
            raise ValidationError("Prepared source sellability count changed")
        for row in self.rows["data/StockOnHand_cleaned.csv"]:
            if (
                _required(row, "ProductCode") not in known
                or exact_quantity(_required(row, "Quantity")) < 0
            ):
                raise ValidationError("Prepared stock has an unknown product or negative quantity")
            _source_cost(row.get("AverageCost", ""))
        for row in self.rows["data/AssemblyBOM_cleaned.csv"]:
            if (
                row.get("ProductSKU") not in known
                or row.get("ComponentSKU") not in known
                or exact_quantity(row.get("Quantity")) <= 0
            ):
                raise ValidationError("Prepared recipe has an unknown product or invalid quantity")
        for kind in ("Customer", "Supplier"):
            parties = {_key(row["Name"]) for row in self.rows[f"data/{kind}s_cleaned.csv"]}
            for suffix, owner in (("Contacts", kind), ("Addresses", "Name")):
                for row in self.rows[f"data/{kind}{suffix}_cleaned.csv"]:
                    if _key(_required(row, owner)) not in parties:
                        raise ValidationError("Prepared contact/address owner is unknown")

    def payload(
        self, file: str, identity: tuple[str, str, str], rows: list[dict[str, str]]
    ) -> dict:
        return {
            "format": "cin7-prepared-v1",
            "manifest_sha256": self.manifest_sha256,
            "source_file": file,
            "source_file_sha256": self.manifest["import_candidate_files"][file]["sha256"],
            "identity": {"party": identity[0], "number": identity[1], "date": identity[2]},
            "identity_sha256": hashlib.sha256(
                json.dumps(identity, ensure_ascii=False).encode()
            ).hexdigest(),
            "rows": rows,
        }


@dataclass(frozen=True)
class BinMapping:
    source_location: str
    source_bin: str
    location_id: uuid.UUID
    bin_id: uuid.UUID
    target_location_name: Optional[str] = None
    target_bin_code: Optional[str] = None


async def validate_bin_mappings(
    db: AsyncSession, package: PreparedPackage, mappings: list[BinMapping]
) -> None:
    keys = [(item.source_location, item.source_bin) for item in mappings]
    required = {
        (row.get("Location", ""), row.get("Bin", ""))
        for row in package.rows["data/StockOnHand_cleaned.csv"]
    }
    if len(keys) != len(set(keys)) or set(keys) != required:
        raise ValidationError("Bin mapping must cover each exact source location/bin pair once")
    for item in mappings:
        location = await db.scalar(
            select(Location).where(
                Location.id == item.location_id, Location.team_id == tenant_id_ctx.get()
            )
        )
        bin_row = await db.scalar(
            select(LocationBin).where(
                LocationBin.id == item.bin_id, LocationBin.team_id == tenant_id_ctx.get()
            )
        )
        if location is None or bin_row is None or bin_row.location_id != location.id:
            raise ValidationError("Bin mapping references an unknown or foreign location/bin")
        if location.is_archived or bin_row.is_archived:
            raise ValidationError("Bin mapping references an archived location/bin")
        if item.target_location_name is not None and location.name != item.target_location_name:
            raise ValidationError("Mapped location name differs from the approved source mapping")
        if item.target_bin_code is not None and bin_row.code != item.target_bin_code:
            raise ValidationError("Mapped bin code differs from the approved source mapping")


class PreparedLoader:
    def __init__(self, db: AsyncSession, package: PreparedPackage, mappings: list[BinMapping]):
        self.db, self.package, self.mappings = db, package, mappings
        self.counts: dict[str, int] = {}

    async def run(self) -> dict:
        if tenant_id_ctx.get() is None:
            raise ValidationError("Prepared load requires an explicit tenant")
        await validate_bin_mappings(self.db, self.package, self.mappings)
        # Keep physical product identities used by commerce and existing photo objects.
        # Every other old business field is replaced from this reviewed source.
        for sku in await self.db.scalars(select(Sku).where(Sku.team_id == tenant_id_ctx.get())):
            sku.design = f"cin7:{sku.our_ref}"
            sku.fabric = "-"
            sku.supplier_ref = None
            sku.preferred_supplier_id = None
            sku.lead_time_days = None
            sku.reorder_min = None
            sku.category = None
            sku.stockist_ex_vat = None
            sku.wholesale_ex_vat = None
            sku.decorator_ex_vat = None
            sku.retail_ex_vat = None
            sku.carton_count = 1
            sku.made_to_order_capacity = None
            sku.made_to_order_lead_time_min_days = None
            sku.made_to_order_lead_time_max_days = None
            sku.made_to_order_expires_at = None
            sku.made_to_order_offer_id = None
        await self.db.flush()
        with tempfile.TemporaryDirectory(prefix="firstout-prepared-masters-") as directory:
            stage = Path(directory)
            for relative in MASTER_FILES:
                target = stage / Path(relative).name
                raw = self.package.verified_bytes[relative]
                if relative in {"data/Customers_cleaned.csv", "data/Suppliers_cleaned.csv"}:
                    fields = [
                        field
                        for field in next(csv.reader(io.StringIO(raw.decode("utf-8-sig"))))
                        if field != "is_archived" and not field.startswith("_stage_source_")
                    ]
                    with target.open("w", newline="", encoding="utf-8") as handle:
                        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
                        writer.writeheader()
                        writer.writerows(self.package.rows[relative])
                else:
                    target.write_bytes(raw)
            report = await run_import(self.db, stage, price_tiers=(1, 2, 3, 4))
        bad_skips = {
            name: result.skipped
            for name, result in report.entities.items()
            if result.skipped
            and name
            in {
                "sku",
                "customer",
                "supplier",
                "customer_contact",
                "customer_address",
                "supplier_contact",
                "supplier_address",
                "sku_bom_line",
                "sku_supplier_price",
            }
        }
        if report.errors or bad_skips:
            raise ValidationError("Prepared master load skipped required source records")
        self.customers = {
            _key(row.name): row
            for row in await self.db.scalars(
                select(Customer).where(Customer.team_id == tenant_id_ctx.get())
            )
        }
        self.suppliers = {
            _key(row.name): row
            for row in await self.db.scalars(
                select(Supplier).where(Supplier.team_id == tenant_id_ctx.get())
            )
        }
        self.skus = {
            row.our_ref: row
            for row in await self.db.scalars(select(Sku).where(Sku.team_id == tenant_id_ctx.get()))
        }
        for plural, entities in (("Customers", self.customers), ("Suppliers", self.suppliers)):
            for row in self.package.rows[f"data/{plural}_cleaned.csv"]:
                entity = entities[_key(row["Name"])]
                entity.is_archived = _archived(row["is_archived"])
                if plural == "Suppliers":
                    entity.vat_number = normalize_vat_number(row.get("TaxNumber"))
        await self._stock()
        await self._sales_documents()
        await self._sales_orders()
        await self._purchase_orders()
        await self._purchase_documents()
        await self.db.flush()
        await self._assert_counts()
        return {
            "manifest_sha256": self.package.manifest_sha256,
            "rows": self.counts,
            "historical_operations_created": False,
            "media_loaded": False,
            "stock": self.stock_evidence,
            "ignored_positive_reference_tiers": {
                str(tier): sum(
                    Decimal(row.get(f"PriceTier{tier}") or "0") > 0
                    for row in self.package.rows["data/InventoryList_cleaned.csv"]
                )
                for tier in range(5, 11)
            },
        }

    def _sku(self, row: dict[str, str], *, blank_allowed: bool = False) -> Optional[Sku]:
        code = row.get("SKU", "").strip()
        if not code and blank_allowed:
            return None
        if code not in self.skus:
            raise ValidationError("Canonical history has an unknown product reference")
        return self.skus[code]

    def _groups(self, file: str, party: str, number: str, date: str):
        groups: dict[tuple[str, str, str], list[dict[str, str]]] = {}
        for row in self.package.rows[file]:
            identity = (
                _key(_required(row, party)),
                _required(row, number),
                _day(_required(row, date)).isoformat(),
            )
            window = self.package.manifest["fixed_history_window"]
            if not window["from_inclusive"] <= identity[2] <= window["as_of"]:
                raise ValidationError(
                    "Canonical history document is outside the reviewed date window"
                )
            groups.setdefault(identity, []).append(row)
        return groups.items()

    async def _add(self, entity) -> None:
        self.db.add(entity)
        await self.db.flush()

    async def _stock(self) -> None:
        source = self.package.rows["data/StockOnHand_cleaned.csv"]
        # Size the context for exact finite source products and their sums. Only
        # division for the stored unit cost needs final four-place rounding.
        products = [
            (exact_quantity(row["Quantity"]), cost)
            for row in source
            if (cost := _source_cost(row.get("AverageCost", ""))) is not None
        ]
        highest = max((qty.adjusted() + cost.adjusted() + 2 for qty, cost in products), default=1)
        lowest = min(
            (qty.as_tuple().exponent + cost.as_tuple().exponent for qty, cost in products),
            default=0,
        )
        with localcontext() as context:
            context.prec = max(28, highest - lowest + len(str(len(source))) + 10)
            await self._stock_in_context()

    async def _stock_in_context(self) -> None:
        mapping = {(item.source_location, item.source_bin): item for item in self.mappings}
        bin_totals = defaultdict(lambda: ZERO)
        location_parts = defaultdict(list)
        source_lot_value = ZERO
        source_value = ZERO
        stored_value = ZERO
        source_qty = ZERO
        unknown_cost_rows = 0
        for row in self.package.rows["data/StockOnHand_cleaned.csv"]:
            sku = self.skus[_required(row, "ProductCode")]
            target = mapping[(row.get("Location", ""), row.get("Bin", ""))]
            qty = exact_quantity(row["Quantity"])
            source_qty += qty
            cost = _source_cost(row.get("AverageCost", ""))
            bin_totals[(sku.id, target.bin_id)] += qty
            location_parts[(sku.id, target.location_id)].append((qty, cost))
            if cost is not None:
                source_lot_value += qty * cost
            elif qty > 0:
                unknown_cost_rows += 1
        for (sku_id, bin_id), qty in bin_totals.items():
            await self._add(BinStock(sku_id=sku_id, bin_id=bin_id, on_hand=exact_quantity(qty)))
        for (sku_id, location_id), parts in location_parts.items():
            qty = exact_quantity(sum(part[0] for part in parts))
            cost = None
            if qty > 0 and all(c is not None for q, c in parts if q > 0):
                exact_value = sum(q * c for q, c in parts if c is not None)
                source_value += exact_value
                cost = (exact_value / qty).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
                stored_value += qty * cost
            await self._add(
                LocationStock(
                    sku_id=sku_id, location_id=location_id, on_hand=qty, unit_cost_zar=cost
                )
            )
        self.counts.update(
            stock_source_rows=len(self.package.rows["data/StockOnHand_cleaned.csv"]),
            bin_stock=len(bin_totals),
            location_stock=len(location_parts),
        )
        self.stock_evidence = {
            "quantity": str(source_qty),
            "known_cost_value": str(source_lot_value),
            "source_known_lot_value": str(source_lot_value),
            "source_exact_known_value": str(source_value),
            "stored_known_value": str(stored_value),
            "stored_minus_source_value": str(stored_value - source_value),
            "unit_cost_rounding": "HALF_UP to 4 decimal places after exact source weighting; quantities unchanged",
            "unknown_cost_rows": unknown_cost_rows,
        }

    async def _sales_documents(self) -> None:
        file = "history/SaleInvoicesCreditNotes.csv"
        seen = set()
        for identity, rows in self._groups(file, "Customer", "Document #", "Date"):
            party, number, day = identity
            if number in seen or party not in self.customers:
                raise ValidationError("Sales document identity collides or its customer is unknown")
            seen.add(number)
            customer = self.customers[party]
            credit = number.upper().startswith("CR")
            if len(number) > (64 if credit else 32):
                raise ValidationError("Sales document number exceeds storage capacity")
            totals = [ZERO, ZERO, ZERO]
            lines = []
            for index, row in enumerate(rows):
                sku = self._sku(row, blank_allowed=True)
                qty = (
                    exact_quantity(_required(row, "Quantity"))
                    if credit
                    else _whole(_required(row, "Quantity"))
                )
                net, tax, gross = (
                    _amount(_required(row, field)) for field in ("Amount", "Tax", "Total")
                )
                if net + tax != gross:
                    raise ValidationError("Sales source net/tax/gross do not reconcile")
                for i, value in enumerate((net, tax, gross)):
                    totals[i] += value
                description = _required(row, "Product", 512)
                if credit:
                    lines.append(
                        ArchiveCreditNoteLine(
                            sku_id=sku.id if sku else None,
                            sku_code=row.get("SKU") or None,
                            description=description,
                            qty=qty,
                            ex_vat=net,
                            vat_amount=tax,
                            inc_vat=gross,
                            sort_order=index,
                        )
                    )
                else:
                    lines.append(
                        InvoiceLine(
                            sku_id=sku.id if sku else None,
                            description=description,
                            qty=qty,
                            unit_ex_vat=(net / qty).quantize(CENT, rounding=ROUND_HALF_UP),
                            ex_vat=net,
                            vat_amount=tax,
                            inc_vat=gross,
                            sort_order=index,
                        )
                    )
            common = dict(
                customer_id=customer.id,
                issue_date=datetime.date.fromisoformat(day),
                subtotal_ex_vat=totals[0],
                vat_amount=totals[1],
                total_inc_vat=totals[2],
                cin7_source_payload=self.package.payload(file, identity, rows),
                lines=lines,
            )
            entity = (
                ArchiveCreditNote(document_number=number, source="cin7", **common)
                if credit
                else TaxInvoice(
                    invoice_number=number,
                    is_archive=True,
                    amount_paid=ZERO,
                    prices_include_vat=shows_prices_including_vat(customer),
                    **common,
                )
            )
            await self._add(entity)
            key = "archive_credit_notes" if credit else "tax_invoices"
            self.counts[key] = self.counts.get(key, 0) + 1
            self.counts[key + "_lines"] = self.counts.get(key + "_lines", 0) + len(rows)

    async def _sales_orders(self) -> None:
        file = "history/SaleOrderDetails.csv"
        seen = set()
        for identity, rows in self._groups(file, "Customer", "Order #", "Order date"):
            party, number, day = identity
            if number in seen or party not in self.customers:
                raise ValidationError("Sales order identity collides or its customer is unknown")
            seen.add(number)
            statuses = {row["Status"].strip().lower() for row in rows}
            if len(statuses) != 1 or next(iter(statuses)) not in SO_STATUS:
                raise ValidationError("Sales order source status is unsupported or inconsistent")
            customer = self.customers[party]
            lines = []
            for row in rows:
                sku = self._sku(row)
                lines.append(
                    SalesOrderLine(
                        sku_id=sku.id,
                        qty=_whole(row["Quantity Total"]),
                        unit_ex_vat=ZERO,
                        description=_required(row, "Product", 512),
                        held_qty=0,
                    )
                )
            await self._add(
                SalesOrder(
                    so_number=number,
                    customer_id=customer.id,
                    status=SO_STATUS[next(iter(statuses))],
                    is_archive=True,
                    hold_stock=False,
                    awaiting_stock=False,
                    subtotal_ex_vat=ZERO,
                    vat_amount=ZERO,
                    total_inc_vat=ZERO,
                    amount_paid=ZERO,
                    prices_include_vat=shows_prices_including_vat(customer),
                    notes=f"Cin7 archive {day}. Source report supplies quantities only; prices and totals unavailable.",
                    cin7_source_payload={
                        **self.package.payload(file, identity, rows),
                        "facts": {"amounts_known": False, "currency_known": False},
                    },
                    lines=lines,
                )
            )
            self.counts["sales_orders"] = self.counts.get("sales_orders", 0) + 1
            self.counts["sales_order_lines"] = self.counts.get("sales_order_lines", 0) + len(lines)

    async def _purchase_orders(self) -> None:
        file = "history/PurchaseOrderDetails.csv"
        seen = set()
        for identity, rows in self._groups(file, "Supplier", "PO #", "PO date"):
            party, number, day = identity
            if number in seen or party not in self.suppliers or len(number) > 32:
                raise ValidationError(
                    "Purchase order identity collides, exceeds capacity or has unknown supplier"
                )
            seen.add(number)
            statuses = {row["Status"].strip().lower() for row in rows}
            if len(statuses) != 1 or next(iter(statuses)) not in PO_STATUS:
                raise ValidationError("Purchase order source status is unsupported or inconsistent")
            if len({row.get("SKU", "").strip() for row in rows}) != len(rows):
                raise ValidationError(
                    "Purchase order has duplicate SKU source rows; source cost binding is ambiguous"
                )
            lines = []
            for row in rows:
                sku = self._sku(row)
                qty = exact_quantity(row["Quantity"])
                if qty <= 0:
                    raise ValidationError("Purchase order quantity must be positive")
                lines.append(
                    PoLine(
                        sku_id=sku.id,
                        qty=qty,
                        # Report Cost/Total do not consistently define an
                        # operational unit price and may exceed money precision.
                        # Preserve both original strings in provenance instead.
                        factory_unit_amount=None,
                    )
                )
            payload = self.package.payload(file, identity, rows)
            payload["currency_verification"] = "not supplied by source report"
            payload["facts"] = {
                "amounts_known": False,
                "currency_known": False,
                "raw_costs_available": True,
            }
            await self._add(
                PurchaseOrder(
                    po_number=number,
                    supplier_id=self.suppliers[party].id,
                    status=PO_STATUS[next(iter(statuses))],
                    is_archive=True,
                    ordered_at=datetime.datetime.combine(
                        datetime.date.fromisoformat(day),
                        datetime.time(),
                        tzinfo=datetime.timezone.utc,
                    ),
                    notes="Cin7 archive. Original report Cost/Total are retained as source strings; verified operational prices and historical currency were not supplied. No receiving or financial posting.",
                    cin7_source_payload=payload,
                    lines=lines,
                )
            )
            self.counts["purchase_orders"] = self.counts.get("purchase_orders", 0) + 1
            self.counts["po_lines"] = self.counts.get("po_lines", 0) + len(lines)

    async def _purchase_documents(self) -> None:
        file = "history/PurchaseInvoicesCreditNotes.csv"
        for identity, rows in self._groups(file, "Supplier", "Document #", "Date"):
            party, number, day = identity
            if party not in self.suppliers or len(number) > 128:
                raise ValidationError(
                    "Purchase invoice has an unknown supplier or overlong original reference"
                )
            currencies = {_required(row, "Currency", 8).strip().upper() for row in rows}
            if len(currencies) != 1 or next(iter(currencies)) not in {
                "ZAR",
                "USD",
                "EUR",
                "GBP",
                "AUD",
                "CNY",
            }:
                raise ValidationError("Purchase invoice currency is unknown or inconsistent")
            currency = next(iter(currencies))
            lines = []
            total = ZERO
            for index, row in enumerate(rows):
                self._sku(row, blank_allowed=True)
                qty = exact_quantity(_required(row, "Quantity"))
                net, tax, gross = (
                    _amount(_required(row, field)) for field in ("Amount", "Tax", "Total")
                )
                if net + tax != gross:
                    raise ValidationError("Purchase source net/tax/gross do not reconcile")
                total += gross
                lines.append(
                    BillLine(
                        description=_required(row, "Product", 512),
                        qty=qty,
                        unit_amount=(gross / qty).quantize(CENT, rounding=ROUND_HALF_UP)
                        if qty
                        else ZERO,
                        amount_foreign=gross,
                        sort_order=index,
                    )
                )
            payload = self.package.payload(file, identity, rows)
            internal = "CIN7-" + payload["identity_sha256"]
            await self._add(
                Bill(
                    bill_number=internal,
                    supplier_id=self.suppliers[party].id,
                    supplier_ref=number,
                    issue_date=datetime.date.fromisoformat(day),
                    currency=currency,
                    fx_to_zar=Decimal(1) if currency == "ZAR" else ZERO,
                    fx_rate_known=currency == "ZAR",
                    amount_foreign=total,
                    amount_zar=total if currency == "ZAR" else ZERO,
                    amount_paid_zar=ZERO,
                    amount_paid_foreign=ZERO,
                    is_archive=True,
                    cin7_source_payload=payload,
                    lines=lines,
                )
            )
            self.counts["bills"] = self.counts.get("bills", 0) + 1
            self.counts["bill_lines"] = self.counts.get("bill_lines", 0) + len(lines)

    async def _assert_counts(self) -> None:
        expected = self.package.manifest["counts"]
        for model, key in ((Customer, "Customers"), (Supplier, "Suppliers")):
            active = await self.db.scalar(
                select(func.count())
                .select_from(model)
                .where(model.team_id == tenant_id_ctx.get(), model.is_archived.is_(False))
            )
            archived = await self.db.scalar(
                select(func.count())
                .select_from(model)
                .where(model.team_id == tenant_id_ctx.get(), model.is_archived.is_(True))
            )
            if (active, archived) != (expected[key]["active"], expected[key]["archived"]):
                raise ValidationError("Prepared party post-load counts do not match")
        products = await self.db.scalar(
            select(func.count()).select_from(Sku).where(Sku.team_id == tenant_id_ctx.get())
        )
        if products != expected["products"]:
            raise ValidationError("Prepared product post-load count does not match")
        nonsale = await self.db.scalar(
            select(func.count())
            .select_from(Sku)
            .where(Sku.team_id == tenant_id_ctx.get(), Sku.is_sellable.is_(False))
        )
        if nonsale != expected["nonsellable_source_products"]:
            raise ValidationError("Prepared nonsellable post-load count does not match")
        product_rows = self.package.rows["data/InventoryList_cleaned.csv"]
        tiers = {
            tier
            for tier in range(1, 5)
            if any(Decimal(row.get(f"PriceTier{tier}") or "0") > 0 for row in product_rows)
        }
        names = set(
            await self.db.scalars(
                select(PriceList.name).where(PriceList.team_id == tenant_id_ctx.get())
            )
        )
        if names != {tier_price_list_name(tier) for tier in tiers}:
            raise ValidationError(
                "Prepared price lists differ from the four supported classifications"
            )
        items = await self.db.scalar(
            select(func.count())
            .select_from(PriceListItem)
            .where(PriceListItem.team_id == tenant_id_ctx.get())
        )
        if items != sum(
            Decimal(row.get(f"PriceTier{tier}") or "0") > 0
            for row in product_rows
            for tier in range(1, 5)
        ):
            raise ValidationError("Prepared valid price item count does not match")
        self.counts.update(price_lists=len(names), price_list_items=items)
        expected_qty = Decimal(self.stock_evidence["quantity"])
        for model in (LocationStock, BinStock):
            actual_qty = await self.db.scalar(
                select(func.coalesce(func.sum(model.on_hand), 0)).where(
                    model.team_id == tenant_id_ctx.get()
                )
            )
            if actual_qty != expected_qty:
                raise ValidationError(
                    "Prepared location/bin quantity rollups differ from the exact source"
                )
