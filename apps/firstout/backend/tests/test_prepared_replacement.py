"""Synthetic package replacement on migrated PostgreSQL with real non-owner RLS."""

from __future__ import annotations

import csv
import json
import datetime
import io
import os
import subprocess
import sys
import uuid
import zipfile
from decimal import Decimal
from pathlib import Path

import pytest
import pytest_asyncio
import sqlalchemy as sa
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.commands.replace_primavera import (
    KNOWN,
    EXTERNAL_PRESERVE,
    SCHEMA_REVISION,
    PRIMAVERA_TEAM_ID,
    _snapshot,
    read_mapping,
    replace_in_transaction,
)
from app.database import TenantSession
from app.models.bill import Bill
from app.models.archive_credit_note import ArchiveCreditNote, ArchiveCreditNoteLine
from app.models.customer import Customer
from app.models.customer_portal_user import CustomerPortalUser
from app.models.cin7_import_run import Cin7ImportRun
from app.models.ops_commerce_refund import OpsCommerceRefundEvent
from app.models.purchase_order import PurchaseOrder
from app.models.sales_order import SalesOrder
from app.models.tax_invoice import TaxInvoice
from app.models.inventory import LocationStock
from app.models.location import Location, LocationType
from app.models.location_bin import new_floor_bin
from app.models.membership import Membership
from app.models.record_workspace import RecordWorkspaceBatch
from app.models.role import Role
from app.models.sku import Sku
from app.models.team import Team
from app.models.team_settings import TeamSettings
from app.models.user import User
from app.services.cin7_import.prepared import (
    CANDIDATE_FILES,
    EVIDENCE_FILES,
    PreparedPackage,
    file_sha256,
)
from f0rge_core.exceptions import ValidationError
from f0rge_core.exceptions import ConflictError
from f0rge_db.organisation import organisation_session
from tests.test_fractional_inventory_migration import migrate

pytestmark = pytest.mark.no_db


def write_package(root: Path, *, invalid_history=False, duplicate_po=False):
    data = {
        "data/Customers_cleaned.csv": (
            ["Name", "Status", "PriceTier", "is_archived"],
            [
                ["Active customer", "Active", "Retail", "false"],
                ["Dormant customer", "Active", "Stockist", "true"],
            ],
        ),
        "data/Suppliers_cleaned.csv": (
            ["Name", "Currency", "is_archived"],
            [["Active supplier", "ZAR", "false"], ["Dormant supplier", "USD", "true"]],
        ),
        "data/CustomerContacts_cleaned.csv": (["Customer", "Contact", "Email", "Default"], []),
        "data/SupplierContacts_cleaned.csv": (["Supplier", "Contact", "Email", "Default"], []),
        "data/CustomerAddresses_cleaned.csv": (["Name", "AddressLine1"], []),
        "data/SupplierAddresses_cleaned.csv": (["Name", "AddressLine1"], []),
        "data/InventoryList_cleaned.csv": (
            ["ProductCode", "Name", "Barcode", "PriceTier4", "PriceTier5", "Sellable"],
            [
                ["RETAIN", "Retained source product", "RETAIN-BAR", "115", "999", "Yes"],
                ["MATERIAL", "Material stock", "MATERIAL-BAR", "", "", "No"],
            ],
        ),
        "data/StockOnHand_cleaned.csv": (
            ["ProductCode", "Quantity", "AverageCost", "Location", "Bin"],
            [
                ["RETAIN", "0.25", "100.0000", "Source", "A"],
                ["RETAIN", "0.125", "0.0000", "Source", "A"],
                ["RETAIN", "0.125", "100.1234567890123", "Source", ""],
            ],
        ),
        "data/AssemblyBOM_cleaned.csv": (["ProductSKU", "ComponentSKU", "Quantity"], []),
        "data/ProductPriceBySupplier_cleaned.csv": (
            ["SKU", "Supplier", "SupplierSKU", "LatestPrice", "FixedPrice"],
            [],
        ),
        "history/SaleInvoicesCreditNotes.csv": (
            [
                "Document #",
                "Customer",
                "Date",
                "SKU",
                "Product",
                "Quantity",
                "Amount",
                "Tax",
                "Total",
                "_source_file",
                "_source_row",
            ],
            [
                [
                    "INV-1",
                    "Active customer",
                    "2026-11-14",
                    "UNKNOWN" if invalid_history else "RETAIN",
                    "Source sale",
                    "1",
                    "100.01",
                    "15.0015",
                    "115.0115",
                    "synthetic.xlsx",
                    "2",
                ],
                [
                    "CR-1",
                    "Active customer",
                    "2026-11-14",
                    "RETAIN",
                    "Source credit",
                    "-1",
                    "-100.01",
                    "-15.0015",
                    "-115.0115",
                    "synthetic.xlsx",
                    "3",
                ],
                [
                    "INV-1",
                    "Active customer",
                    "2026-11-14",
                    "RETAIN",
                    "Second source sale",
                    "1",
                    "5.01",
                    "0.7515",
                    "5.7615",
                    "synthetic.xlsx",
                    "4",
                ],
                [
                    "CR-1",
                    "Active customer",
                    "2026-11-14",
                    "RETAIN",
                    "Second source credit",
                    "-1",
                    "-5.01",
                    "-0.7515",
                    "-5.7615",
                    "synthetic.xlsx",
                    "5",
                ],
            ],
        ),
        "history/SaleOrderDetails.csv": (
            ["Order #", "Customer", "Order date", "Status", "SKU", "Product", "Quantity Total"],
            [["SO-1", "Active customer", "2026-11-14", "Ordered", "RETAIN", "Source order", "1"]],
        ),
        "history/PurchaseOrderDetails.csv": (
            [
                "PO #",
                "Supplier",
                "PO date",
                "Status",
                "SKU",
                "Product",
                "Quantity",
                "Cost",
                "Total",
            ],
            [
                [
                    "PO-1",
                    "Active supplier",
                    "2026-11-14",
                    "Receiving",
                    "RETAIN",
                    "Source purchase",
                    "4.576",
                    "100.1234567890123",
                    "457.60",
                ]
            ],
        ),
        "history/PurchaseInvoicesCreditNotes.csv": (
            [
                "Document #",
                "Supplier",
                "Date",
                "SKU",
                "Product",
                "Currency",
                "Quantity",
                "Amount",
                "Tax",
                "Total",
                "_source_file",
                "_source_row",
            ],
            [
                [
                    "DUPLICATE",
                    "Active supplier",
                    "2025-01-01",
                    "RETAIN",
                    "Source bill",
                    "USD",
                    "4.576",
                    "100.00",
                    "15.00",
                    "115.00",
                    "synthetic-purchase.xlsx",
                    "2",
                ],
                [
                    "DUPLICATE",
                    "Active supplier",
                    "2025-02-01",
                    "RETAIN",
                    "Source bill",
                    "ZAR",
                    "1",
                    "200.00",
                    "30.00",
                    "230.00",
                    "synthetic-purchase.xlsx",
                    "3",
                ],
            ],
        ),
    }
    if duplicate_po:
        repeated = list(data["history/PurchaseOrderDetails.csv"][1][0])
        repeated[7] = "999.9876543210987"
        data["history/PurchaseOrderDetails.csv"][1].append(repeated)
    specs = {}
    for relative in sorted(CANDIDATE_FILES | EVIDENCE_FILES):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        headers, rows = data.get(relative, (["Evidence"], []))
        with path.open("w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(headers)
            writer.writerows(rows)
        specs[relative] = {"sha256": file_sha256(path), "rows": len(rows)}
    manifest = {
        "schema_version": 1,
        "package_kind": "firstout_primavera_filtered_operational_staging",
        "guard": {"production_import_allowed": False},
        "fixed_history_window": {"from_inclusive": "2024-11-14", "as_of": "2026-11-14"},
        "import_candidate_files": {k: v for k, v in specs.items() if k in CANDIDATE_FILES},
        "evidence_files_never_import": {k: v for k, v in specs.items() if k in EVIDENCE_FILES},
        "counts": {
            "Customers": {"total": 2, "active": 1, "archived": 1},
            "Suppliers": {"total": 2, "active": 1, "archived": 1},
            "products": 2,
            "nonsellable_source_products": 1,
        },
    }
    path = root / "StageManifest.json"
    path.write_text(json.dumps(manifest, sort_keys=True))
    return PreparedPackage.read(root, file_sha256(path))


@pytest_asyncio.fixture
async def replacement_database(second_postgres_url, monkeypatch):
    from app.config import settings
    from app.commands.tenant_cutover import activate_rls

    monkeypatch.setattr(settings, "frontend_proxy_secret", "synthetic-replacement-proxy")
    migrate(second_postgres_url, "091_sku_archive")
    admin = create_async_engine(second_postgres_url)
    role = "prepared_runtime_" + uuid.uuid4().hex[:12]
    password = "synthetic-" + uuid.uuid4().hex
    async with admin.begin() as conn:
        await conn.execute(
            sa.text(f"CREATE ROLE \"{role}\" LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD '{password}'")
        )
        await conn.execute(sa.text(f'GRANT USAGE ON SCHEMA public TO "{role}"'))
        await conn.execute(
            sa.text(f'GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA public TO "{role}"')
        )
        await conn.execute(
            sa.text(f'GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA public TO "{role}"')
        )
        await conn.execute(
            sa.text(f'REVOKE INSERT,UPDATE,DELETE ON release_migration_receipts FROM "{role}"')
        )
        await conn.execute(
            sa.text(
                "INSERT INTO release_migration_receipts "
                "(source_commit,schema_revision,policy_sha256,from_revision,completed_at) "
                "VALUES (:commit,:revision,:policy,'089_merge_record_workspaces','2026-11-15 12:00:00')"
            ),
            {"commit": "a" * 40, "revision": SCHEMA_REVISION, "policy": "b" * 64},
        )
    runtime = create_async_engine(
        make_url(second_postgres_url).set(username=role, password=password)
    )
    maker = async_sessionmaker(runtime, expire_on_commit=False, sync_session_class=TenantSession)
    async with AsyncSession(admin) as owner, maker() as session:
        await activate_rls(owner, session)
        await owner.commit()
        await session.rollback()
    async with AsyncSession(admin, expire_on_commit=False) as db:
        migrated_home = await db.scalar(sa.select(Team).where(Team.slug == "firstout"))
        if migrated_home is not None:
            migrated_home.slug = "migration-seed-home"
            await db.flush()
        target = Team(
            id=PRIMAVERA_TEAM_ID, name="Primavera Pty Ltd", slug="firstout", status="maintenance"
        )
        other = Team(name="Synthetic sentinel", slug="sentinel", status="active")
        db.add_all([target, other])
        await db.flush()
        a = Location(
            team_id=target.id, name="Old warehouse", type=LocationType.WAREHOUSE, is_archived=False
        )
        b = Location(
            team_id=target.id,
            name="Old placeholder",
            type=LocationType.WAREHOUSE,
            is_archived=False,
        )
        db.add_all([a, b])
        await db.flush()
        bins = [new_floor_bin(a.id), new_floor_bin(b.id)]
        for row in bins:
            row.team_id = target.id
        db.add_all(bins)
        owner = User(
            team_id=target.id,
            email="replacement-owner@example.com",
            password_hash="synthetic",
            role="owner",
            default_location_id=a.id,
        )
        db.add(owner)
        await db.flush()
        db.add(
            Membership(
                user_id=owner.id,
                team_id=target.id,
                role="owner",
                is_legacy_home=True,
                default_location_id=a.id,
            )
        )
        db.add(
            Role(
                team_id=target.id, slug="owner", name="Owner", is_system=True, is_owner_preset=True
            )
        )
        db.add(
            TeamSettings(
                team_id=target.id,
                default_receive_location_id=a.id,
                default_till_location_id=b.id,
                pick_priority=[str(a.id), str(b.id)],
            )
        )
        retained = Sku(
            team_id=target.id,
            our_ref="RETAIN",
            our_barcode="OLD-BAR",
            name="Old source title",
            design="Old design",
            fabric="Old fabric",
            storefront_published=True,
            photo_storage_key="synthetic/photo.jpg",
            retail_ex_vat=Decimal(999),
            lead_time_days=99,
        )
        excluded = Sku(
            team_id=target.id,
            our_ref="OLD-EXCLUDED",
            our_barcode="OLD-EXCLUDED",
            name="Remove old",
            design="Remove old",
            fabric="Old",
        )
        sentinel = Sku(
            team_id=other.id,
            our_ref="RETAIN",
            our_barcode="SENTINEL",
            name="Other tenant unchanged",
            design="Other design",
            fabric="Other",
        )
        db.add_all([retained, excluded, sentinel])
        await db.flush()
        db.add(Customer(team_id=target.id, name="Old customer"))
        # These are immutable operation receipts, including record references
        # inside JSON. Replacement retains them even when old domain rows go.
        workspace_receipts = [
            RecordWorkspaceBatch(
                team_id=team_id,
                actor_user_id=owner.id,
                request_id=uuid.uuid4(),
                resource="customers",
                action="archive",
                payload_hash="a" * 64,
                selection=[{"id": str(uuid.uuid4()), "revision": "retained-revision"}],
                result={"completed": True},
            )
            for team_id in (target.id, other.id)
        ]
        db.add_all(workspace_receipts)
        db.add(
            LocationStock(
                team_id=target.id,
                sku_id=retained.id,
                location_id=a.id,
                on_hand=Decimal(50),
                unit_cost_zar=Decimal(999),
            )
        )
        await db.commit()
        info = {
            "locations": [a.id, b.id],
            "bins": [row.id for row in bins],
            "retained": retained.id,
            "workspace_receipts": [row.id for row in workspace_receipts],
            "sentinel": sentinel.id,
            "other": other.id,
            "database": make_url(second_postgres_url).database,
            "runtime_url": make_url(second_postgres_url)
            .set(username=role, password=password)
            .render_as_string(hide_password=False),
        }
    try:
        yield admin, maker, info
    finally:
        await runtime.dispose()
        async with admin.begin() as conn:
            await conn.execute(sa.text(f'DROP OWNED BY "{role}"'))
            await conn.execute(sa.text(f'DROP ROLE "{role}"'))
        await admin.dispose()


def mapping_file(path, info):
    body = {
        "format": "firstout-source-bin-map-v1",
        "target_team_id": str(PRIMAVERA_TEAM_ID),
        "mappings": [
            {
                "source_location": "Source",
                "source_bin": source,
                "target_location_id": str(location),
                "target_location_name": name,
                "target_bin_id": str(bin_id),
                "target_bin_code": "FLOOR",
            }
            for source, location, bin_id, name in zip(
                ["A", ""], info["locations"], info["bins"], ["Warehouse", "Unassigned"]
            )
        ],
        "location_updates": [
            {"id": str(location), "expected_name": old, "name": name, "is_archived": False}
            for location, old, name in zip(
                info["locations"], ["Old warehouse", "Old placeholder"], ["Warehouse", "Unassigned"]
            )
        ],
        "archive_location_ids": [],
    }
    path.write_text(json.dumps(body))
    return read_mapping(path, file_sha256(path)), file_sha256(path)


async def test_replacement_dry_run_rollback_commit_and_sentinel_isolation(
    replacement_database, tmp_path
):
    admin, maker, info = replacement_database
    package = write_package(tmp_path / "package")
    (mappings, changes), mapping_hash = mapping_file(tmp_path / "map.json", info)
    async with organisation_session(maker, PRIMAVERA_TEAM_ID) as db:
        before = await _snapshot(db, PRIMAVERA_TEAM_ID, KNOWN)
        report = await replace_in_transaction(
            db,
            package,
            mappings,
            changes,
            expected_database=info["database"],
            mapping_sha256=mapping_hash,
        )
        assert report["load"]["rows"]["bills"] == 2
        assert report["load"]["rows"]["price_lists"] == 1
        assert report["load"]["ignored_positive_reference_tiers"]["5"] == 1
        assert report["load"]["stock"]["unknown_cost_rows"] == 1
        cost_report = report["load"]["stock"]
        assert Decimal(cost_report["source_exact_known_value"]) == Decimal("12.5154320986265375")
        assert Decimal(cost_report["stored_known_value"]) == Decimal("12.5154375")
        assert Decimal(cost_report["stored_minus_source_value"]) == Decimal("0.0000054013734625")
        assert (
            await db.scalar(
                sa.select(LocationStock.unit_cost_zar).where(
                    LocationStock.location_id == info["locations"][0]
                )
            )
            is None
        )
        bills = list(await db.scalars(sa.select(Bill).order_by(Bill.issue_date)))
        assert len({row.bill_number for row in bills}) == 2 and {
            row.supplier_ref for row in bills
        } == {"DUPLICATE"}
        assert bills[0].cin7_source_payload["rows"][0]["Quantity"] == "4.576"
        assert bills[0].cin7_source_payload["rows"][0]["Tax"] == "15.00"
        assert bills[0].fx_rate_known is False and bills[0].amount_zar == 0
        from app.services.purchase_orders import PurchaseOrderService
        from app.services.sales_orders import SalesOrdersService
        from app.services.payments import PaymentService
        from app.schemas.payment import PaymentCreate

        po = await db.scalar(sa.select(PurchaseOrder))
        po_service = PurchaseOrderService(db)
        detail = await po_service.get(po.id)
        assert (
            detail.is_archive
            and not detail.source_amounts_known
            and not detail.source_currency_known
        )
        assert detail.lines[0].qty == Decimal("4.576")
        assert detail.lines[0].factory_unit_amount is None
        assert detail.lines[0].source_cost == "100.1234567890123"
        assert detail.lines[0].source_total == "457.60"
        with pytest.raises(ConflictError, match="currency"):
            await po_service.purchase_order_pdf(po.id)
        with pytest.raises(ConflictError, match="read-only"):
            await po_service.approve(po.id)
        with pytest.raises(ConflictError, match="read-only"):
            await po_service.packing_sheet(po.id)
        from app.services.home import HomeService

        assert await HomeService(db)._sum_on_order_value() == 0
        so = await db.scalar(sa.select(SalesOrder))
        so_detail = await SalesOrdersService(db).get(so.id)
        assert (
            so_detail.is_archive
            and not so_detail.source_amounts_known
            and not so_detail.source_currency_known
        )
        invoice = await db.scalar(sa.select(TaxInvoice))
        for direction, entity in (("in", invoice), ("out", bills[1])):
            with pytest.raises(ConflictError, match="read-only"):
                await PaymentService(db).create(
                    PaymentCreate(
                        direction=direction,
                        invoice_id=entity.id if direction == "in" else None,
                        bill_id=entity.id if direction == "out" else None,
                        amount=1,
                        currency="ZAR",
                        paid_on=datetime.date(2026, 11, 14),
                    )
                )
        await db.rollback()
        assert await _snapshot(db, PRIMAVERA_TEAM_ID, KNOWN) == before
    async with organisation_session(maker, PRIMAVERA_TEAM_ID) as db:
        committed = await replace_in_transaction(
            db,
            package,
            mappings,
            changes,
            expected_database=info["database"],
            mapping_sha256=mapping_hash,
            expected_before=report["before_sha256"],
        )
        assert committed["load"] == report["load"]
        await db.commit()
    async with organisation_session(maker, PRIMAVERA_TEAM_ID) as db:
        from app.services.invoices import InvoiceService
        from app.services.records import RecordsService
        from app.schemas.page import PageParams

        invoice = await db.scalar(sa.select(TaxInvoice))
        reloaded = await InvoiceService(db).get(invoice.id)
        assert reloaded.subtotal_ex_vat == Decimal("105.02")
        assert reloaded.vat_amount == Decimal("15.7530") and reloaded.total_inc_vat == Decimal(
            "120.7730"
        )
        assert reloaded.model_dump(mode="json")["vat_amount"] == "15.7530"
        assert [line.vat_amount for line in reloaded.lines] == [
            Decimal("15.0015"),
            Decimal("0.7515"),
        ]
        assert invoice.cin7_source_payload["rows"][0]["Tax"] == "15.0015"
        credit = await db.scalar(sa.select(ArchiveCreditNote))
        assert credit.vat_amount == Decimal("-15.7530") and credit.total_inc_vat == Decimal(
            "-120.7730"
        )
        credit_lines = list(
            await db.scalars(
                sa.select(ArchiveCreditNoteLine).order_by(ArchiveCreditNoteLine.sort_order)
            )
        )
        assert [line.inc_vat for line in credit_lines] == [Decimal("-115.0115"), Decimal("-5.7615")]
        history = await RecordsService(db).sales_history(PageParams())
        assert sum(line.vat_amount for line in history.items if line.kind == "invoice") == Decimal(
            "15.7530"
        )
        assert sum(line.inc_vat for line in history.items if line.kind == "credit_note") == Decimal(
            "-120.7730"
        )
    async with AsyncSession(admin) as db:
        retained = await db.get(Sku, info["retained"])
        assert retained.name == "Retained source product" and retained.storefront_published is True
        assert (
            retained.photo_storage_key == "synthetic/photo.jpg" and retained.lead_time_days is None
        )
        sentinel = await db.get(Sku, info["sentinel"])
        assert sentinel.name == "Other tenant unchanged"
        receipts = list(
            await db.scalars(
                sa.select(RecordWorkspaceBatch).where(
                    RecordWorkspaceBatch.id.in_(info["workspace_receipts"])
                )
            )
        )
        assert len(receipts) == 2 and all(row.result == {"completed": True} for row in receipts)
        assert all(row.selection[0]["revision"] == "retained-revision" for row in receipts)
        assert await db.scalar(
            sa.select(sa.func.sum(LocationStock.on_hand)).where(
                LocationStock.team_id == PRIMAVERA_TEAM_ID
            )
        ) == Decimal("0.500")
        assert (
            await db.scalar(
                sa.text("SELECT count(*) FROM journal_entries WHERE team_id=:id"),
                {"id": PRIMAVERA_TEAM_ID},
            )
            == 0
        )
        assert (
            await db.scalar(
                sa.text("SELECT count(*) FROM payments WHERE team_id=:id"),
                {"id": PRIMAVERA_TEAM_ID},
            )
            == 0
        )


@pytest.mark.parametrize("failure", ["unknown_sku", "duplicate_po_sku"])
async def test_real_post_delete_source_failure_rolls_entire_replacement_back(
    replacement_database, tmp_path, failure
):
    _admin, maker, info = replacement_database
    package = write_package(
        tmp_path / "package",
        invalid_history=failure == "unknown_sku",
        duplicate_po=failure == "duplicate_po_sku",
    )
    (mappings, changes), mapping_hash = mapping_file(tmp_path / "map.json", info)
    async with organisation_session(maker, PRIMAVERA_TEAM_ID) as db:
        before = await _snapshot(db, PRIMAVERA_TEAM_ID, KNOWN)
        with pytest.raises(
            ValidationError,
            match="unknown product" if failure == "unknown_sku" else "duplicate SKU source rows",
        ):
            await replace_in_transaction(
                db,
                package,
                mappings,
                changes,
                expected_database=info["database"],
                mapping_sha256=mapping_hash,
            )
        await db.rollback()
        assert await _snapshot(db, PRIMAVERA_TEAM_ID, KNOWN) == before


def test_manifest_hash_allowlist_and_source_bytes_are_enforced(tmp_path):
    package = write_package(tmp_path / "package")
    manifest = package.root / "StageManifest.json"
    with pytest.raises(ValidationError, match="manifest hash"):
        PreparedPackage.read(package.root, "0" * 64)
    (package.root / "data/StockOnHand_cleaned.csv").write_text("corrupted")
    with pytest.raises(ValidationError, match="file hash"):
        PreparedPackage.read(package.root, file_sha256(manifest))


@pytest.mark.parametrize(
    "case", ["precision", "nonfinite", "row_capacity", "document_capacity", "reconcile"]
)
def test_static_sales_history_validation_refuses_precision_and_capacity_loss(tmp_path, case):
    package = write_package(tmp_path / "package")
    row = package.rows["history/SaleInvoicesCreditNotes.csv"][0]
    if case == "precision":
        row["Tax"] = "15.00151"
    elif case == "nonfinite":
        row["Tax"] = "NaN"
    elif case in {"row_capacity", "document_capacity"}:
        row.update(
            Amount="1000000000000.00" if case == "row_capacity" else "999999999999.99", Tax="0.0000"
        )
        row["Total"] = row["Amount"]
    else:
        row["Total"] = "115.0116"
    with pytest.raises(ValidationError):
        package.validate_source()


async def test_generic_importers_refuse_prepared_package_profiles_before_any_db_work(tmp_path):
    from app.services.cin7_import.archive import validate_zip
    from app.services.cin7_import.load import run_import

    package = write_package(tmp_path / "package")
    with pytest.raises(ValidationError, match="reviewed Primavera replacement"):
        await run_import(None, package.root / "data")
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("nested/StageManifest.json", "{}")
        handle.writestr("nested/data/Customers_cleaned.csv", "Name\nSynthetic\n")
    with pytest.raises(ValidationError, match="reviewed Primavera replacement"):
        validate_zip(archive.getvalue())
    (package.root / "StageManifest.json").unlink()
    (package.root / "data/Customers_cleaned.csv").write_text(
        "Name,_stage_source_file\nSynthetic,source.csv\n"
    )
    with pytest.raises(ValidationError, match="reviewed Primavera replacement"):
        await run_import(None, package.root / "data")


async def test_snapshot_never_retrieves_raw_customer_settings_or_token_json(replacement_database):
    _admin, maker, _info = replacement_database
    statements = []
    async with organisation_session(maker, PRIMAVERA_TEAM_ID) as db:

        def observe(_conn, _cursor, statement, _parameters, _context, _many):
            statements.append(statement.lower())

        sa.event.listen(db.bind.sync_engine, "before_cursor_execute", observe)
        try:
            result = await _snapshot(
                db, PRIMAVERA_TEAM_ID, {"users", "team_settings", "password_reset_tokens"}
            )
        finally:
            sa.event.remove(db.bind.sync_engine, "before_cursor_execute", observe)
        assert result["tables"]["users"]["count"] == 1
        protected_selects = [
            sql for sql in statements if sql.startswith("select") and "to_jsonb" in sql
        ]
        assert len(protected_selects) == 3 and all(
            sql.startswith("select md5(") for sql in protected_selects
        )
        assert not any("row_to_json" in sql for sql in statements)


async def test_uncommitted_cross_tenant_fault_is_detected_before_commit(
    replacement_database, tmp_path
):
    admin, maker, info = replacement_database
    package = write_package(tmp_path / "package")
    (mappings, changes), mapping_hash = mapping_file(tmp_path / "map.json", info)
    injected = False
    async with organisation_session(maker, PRIMAVERA_TEAM_ID) as db:
        before = await _snapshot(db, PRIMAVERA_TEAM_ID, KNOWN)

        def inject(conn, _cursor, statement, _params, _context, _many):
            nonlocal injected
            if not injected and statement.lower().startswith("delete from"):
                injected = True
                conn.execute(
                    sa.text("SELECT set_config('app.tenant_id', :id, true)"),
                    {"id": str(info["other"])},
                )
                try:
                    conn.execute(
                        sa.update(Sku.__table__)
                        .where(Sku.id == info["sentinel"])
                        .values(name="Injected uncommitted cross-tenant mutation")
                    )
                finally:
                    conn.execute(
                        sa.text("SELECT set_config('app.tenant_id', :id, true)"),
                        {"id": str(PRIMAVERA_TEAM_ID)},
                    )

        sa.event.listen(db.bind.sync_engine, "after_cursor_execute", inject)
        try:
            with pytest.raises(ValidationError, match="other-organisation data changed"):
                await replace_in_transaction(
                    db,
                    package,
                    mappings,
                    changes,
                    expected_database=info["database"],
                    mapping_sha256=mapping_hash,
                )
        finally:
            sa.event.remove(db.bind.sync_engine, "after_cursor_execute", inject)
            await db.rollback()
        assert injected and await _snapshot(db, PRIMAVERA_TEAM_ID, KNOWN) == before
    async with AsyncSession(admin) as db:
        assert (await db.get(Sku, info["sentinel"])).name == "Other tenant unchanged"


@pytest.mark.parametrize(
    "gate",
    [
        "baseline",
        "database",
        "portal",
        "published",
        "unknown_table",
        "active_job",
        "foreign_company",
        "identity",
        "multiple_heads",
    ],
)
async def test_replacement_refusal_gates_leave_business_data_intact(
    replacement_database, tmp_path, gate
):
    admin, maker, info = replacement_database
    package = write_package(tmp_path / "package")
    (mappings, changes), mapping_hash = mapping_file(tmp_path / "map.json", info)
    if gate in {
        "portal",
        "published",
        "unknown_table",
        "active_job",
        "foreign_company",
        "identity",
        "multiple_heads",
    }:
        async with AsyncSession(admin) as db:
            if gate == "multiple_heads":
                await db.execute(
                    sa.text(
                        "INSERT INTO alembic_version(version_num) VALUES ('085_record_workspaces')"
                    )
                )
            elif gate == "portal":
                customer = await db.scalar(
                    sa.select(Customer).where(Customer.team_id == PRIMAVERA_TEAM_ID)
                )
                db.add(
                    CustomerPortalUser(
                        team_id=PRIMAVERA_TEAM_ID,
                        customer_id=customer.id,
                        email="portal-binding@example.com",
                        password_hash="synthetic",
                    )
                )
            elif gate == "published":
                sku = await db.scalar(
                    sa.select(Sku).where(
                        Sku.team_id == PRIMAVERA_TEAM_ID, Sku.our_ref == "OLD-EXCLUDED"
                    )
                )
                sku.storefront_published = True
            elif gate == "unknown_table":
                await db.execute(sa.text("CREATE TABLE unreviewed_business_table (id integer)"))
            elif gate == "identity":
                target = await db.get(Team, PRIMAVERA_TEAM_ID)
                target.name = "Primavera"
            elif gate == "active_job":
                user = await db.scalar(sa.select(User).where(User.team_id == PRIMAVERA_TEAM_ID))
                db.add(
                    Cin7ImportRun(
                        team_id=PRIMAVERA_TEAM_ID,
                        user_id=user.id,
                        user_email=user.email,
                        file_sha256="a" * 64,
                        file_name="synthetic.zip",
                        mode="dry_run",
                        status="running",
                        active_lock=True,
                    )
                )
            else:
                db.add(
                    OpsCommerceRefundEvent(
                        team_id=info["other"],
                        company_id=PRIMAVERA_TEAM_ID,
                        provider_refund_id="foreign-binding",
                        event_key="foreign-binding",
                        referenced_capture_id="synthetic-capture",
                        amount_minor=100,
                        currency_code="ZAR",
                        result_code="success",
                        outcome="succeeded",
                        canonical_sha256="a" * 64,
                        provider_event_at=datetime.datetime(2026, 11, 14),
                        received_at=datetime.datetime(2026, 11, 14),
                        signature_verified=True,
                    )
                )
            await db.commit()
    async with organisation_session(maker, PRIMAVERA_TEAM_ID) as db:
        before = await _snapshot(db, PRIMAVERA_TEAM_ID, KNOWN)
        with pytest.raises(
            ValidationError,
            match="exact reviewed schema revision091_sku_archive"
            if gate == "multiple_heads"
            else None,
        ):
            await replace_in_transaction(
                db,
                package,
                mappings,
                changes,
                expected_database="wrong-database" if gate == "database" else info["database"],
                mapping_sha256=mapping_hash,
                expected_before="0" * 64 if gate == "baseline" else None,
            )
        await db.rollback()
        assert await _snapshot(db, PRIMAVERA_TEAM_ID, KNOWN) == before


async def test_real_cli_dry_run_and_commit_evidence_handshake(replacement_database, tmp_path):
    admin, _maker, info = replacement_database
    package = write_package(tmp_path / "package")
    map_path = tmp_path / "map.json"
    (_mappings, _changes), map_hash = mapping_file(map_path, info)
    command = [
        sys.executable,
        "-m",
        "app.commands.replace_primavera",
        "--team-id",
        str(PRIMAVERA_TEAM_ID),
        "--package",
        str(package.root),
        "--manifest-sha256",
        package.manifest_sha256,
        "--bin-map",
        str(map_path),
        "--mapping-sha256",
        map_hash,
        "--expected-database",
        info["database"],
    ]
    env = {
        **os.environ,
        "DATABASE_URL": info["runtime_url"],
        "DIRECT_DATABASE_URL": info["runtime_url"],
        "JWT_SECRET": "synthetic-replacement-cli",
    }
    root = Path(__file__).resolve().parents[1]
    missing = subprocess.run(
        [*command, "--commit"], cwd=root, env=env, capture_output=True, text=True
    )
    assert missing.returncode == 2 and "Commit requires" in missing.stderr
    preview = subprocess.run(command, cwd=root, env=env, capture_output=True, text=True)
    assert preview.returncode == 0, preview.stderr
    plan = json.loads(preview.stdout)
    assert plan["committed"] is False and plan["dry_run_rolled_back"] is True
    plan_path = tmp_path / "reviewed-plan.json"
    plan_path.write_text(preview.stdout)
    backup = tmp_path / "synthetic-restored-backup.enc"
    backup.write_bytes(b"Synthetic fixture backup independently verified by the test operator")
    evidence = {
        "team_id": str(PRIMAVERA_TEAM_ID),
        "database": info["database"],
        "before_sha256": plan["before_sha256"],
        "restore_verified": True,
        "writes_drained": False,
        "provider_project_id": "synthetic-project",
        "provider_service_id": "synthetic-service",
        "backup_path": str(backup),
        "backup_sha256": file_sha256(backup),
    }
    evidence_path = tmp_path / "backup-evidence.json"
    evidence_path.write_text(json.dumps(evidence))

    def commit_args():
        return [
            *command,
            "--commit",
            "--reviewed-plan",
            str(plan_path),
            "--reviewed-plan-sha256",
            file_sha256(plan_path),
            "--backup-evidence",
            str(evidence_path),
            "--backup-evidence-sha256",
            file_sha256(evidence_path),
        ]

    undrained = subprocess.run(commit_args(), cwd=root, env=env, capture_output=True, text=True)
    assert undrained.returncode == 2 and "write-drain evidence" in undrained.stderr
    evidence["writes_drained"] = True
    evidence_path.write_text(json.dumps(evidence))
    backup.write_bytes(b"Changed backup bytes")
    wrong_backup = subprocess.run(commit_args(), cwd=root, env=env, capture_output=True, text=True)
    assert wrong_backup.returncode == 2 and "backup bytes" in wrong_backup.stderr
    evidence["backup_sha256"] = file_sha256(backup)
    evidence_path.write_text(json.dumps(evidence))
    result = subprocess.run(commit_args(), cwd=root, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["committed"] is True
    async with AsyncSession(admin) as db:
        assert (
            await db.scalar(
                sa.select(sa.func.count())
                .select_from(Bill)
                .where(Bill.team_id == PRIMAVERA_TEAM_ID)
            )
            == 2
        )


async def test_replacement_preserves_external_release_receipts_with_select_only_runtime(
    replacement_database, tmp_path
):
    from app.database import Base

    admin, maker, info = replacement_database
    assert set(EXTERNAL_PRESERVE) == {"release_migration_receipts"}
    assert "release_migration_receipts" not in Base.metadata.tables
    package = write_package(tmp_path / "package")
    (mappings, changes), mapping_hash = mapping_file(tmp_path / "map.json", info)
    async with organisation_session(maker, PRIMAVERA_TEAM_ID) as db:
        can_change = await db.scalar(
            sa.text(
                "SELECT has_table_privilege(current_user, 'public.release_migration_receipts', 'INSERT,UPDATE,DELETE')"
            )
        )
        assert not can_change
        before = await _snapshot(db, PRIMAVERA_TEAM_ID, EXTERNAL_PRESERVE)
        assert before["tables"]["release_migration_receipts"]["count"] == 1
        report = await replace_in_transaction(
            db,
            package,
            mappings,
            changes,
            expected_database=info["database"],
            mapping_sha256=mapping_hash,
        )
        assert report["protected_external"] == before["tables"]
        await db.commit()
        assert await _snapshot(db, PRIMAVERA_TEAM_ID, EXTERNAL_PRESERVE) == before
    async with AsyncSession(admin) as db:
        receipt = (
            await db.execute(
                sa.text(
                    "SELECT source_commit,schema_revision,policy_sha256,from_revision FROM release_migration_receipts"
                )
            )
        ).one()
        assert tuple(receipt) == (
            "a" * 40,
            SCHEMA_REVISION,
            "b" * 64,
            "089_merge_record_workspaces",
        )


@pytest.mark.parametrize("metadata", ["is_archived", "archived_at", "archived_by_id"])
async def test_replacement_refuses_existing_sku_archive_metadata_and_preserves_recipe(
    replacement_database, tmp_path, metadata
):
    from app.models.sku_bom_line import SkuBomLine

    admin, maker, info = replacement_database
    package = write_package(tmp_path / "package")
    (mappings, changes), mapping_hash = mapping_file(tmp_path / "map.json", info)
    async with AsyncSession(admin) as db:
        retained = await db.get(Sku, info["retained"])
        excluded = await db.scalar(
            sa.select(Sku).where(Sku.team_id == PRIMAVERA_TEAM_ID, Sku.our_ref == "OLD-EXCLUDED")
        )
        if metadata == "is_archived":
            retained.is_archived = True
        elif metadata == "archived_at":
            retained.archived_at = datetime.datetime(2026, 11, 15)
        else:
            retained.archived_by_id = await db.scalar(
                sa.select(User.id).where(User.team_id == PRIMAVERA_TEAM_ID)
            )
        db.add(
            SkuBomLine(
                team_id=PRIMAVERA_TEAM_ID,
                parent_sku_id=retained.id,
                component_sku_id=excluded.id,
                qty=Decimal("0.125"),
            )
        )
        await db.commit()
    async with organisation_session(maker, PRIMAVERA_TEAM_ID) as db:
        before = await _snapshot(db, PRIMAVERA_TEAM_ID, KNOWN)
        with pytest.raises(
            ValidationError,
            match="Existing SKU archive state requires a separate reviewed replacement plan",
        ):
            await replace_in_transaction(
                db,
                package,
                mappings,
                changes,
                expected_database=info["database"],
                mapping_sha256=mapping_hash,
            )
        await db.rollback()
        assert await _snapshot(db, PRIMAVERA_TEAM_ID, KNOWN) == before
        recipe = await db.scalar(
            sa.select(SkuBomLine).where(SkuBomLine.parent_sku_id == info["retained"])
        )
        assert recipe is not None and recipe.qty == Decimal("0.125")


async def test_replacement_refuses_old_schema_before_reading_new_sku_columns(
    replacement_database, tmp_path
):
    admin, maker, info = replacement_database
    package = write_package(tmp_path / "package")
    (mappings, changes), mapping_hash = mapping_file(tmp_path / "map.json", info)
    async with admin.begin() as conn:
        await conn.execute(
            sa.text("UPDATE alembic_version SET version_num='089_merge_record_workspaces'")
        )
        # Prove the schema gate fires before even trying to read the new ORM fields.
        await conn.execute(
            sa.text(
                "ALTER TABLE skus DROP COLUMN archived_by_id, DROP COLUMN archived_at, DROP COLUMN is_archived"
            )
        )
    async with organisation_session(maker, PRIMAVERA_TEAM_ID) as db:
        before = await _snapshot(db, PRIMAVERA_TEAM_ID, KNOWN)
        with pytest.raises(ValidationError, match="exact reviewed schema revision091_sku_archive"):
            await replace_in_transaction(
                db,
                package,
                mappings,
                changes,
                expected_database=info["database"],
                mapping_sha256=mapping_hash,
            )
        await db.rollback()
        assert await _snapshot(db, PRIMAVERA_TEAM_ID, KNOWN) == before


async def test_replacement_refuses_unknown_release_receipt_columns(replacement_database, tmp_path):
    admin, maker, info = replacement_database
    package = write_package(tmp_path / "package")
    (mappings, changes), mapping_hash = mapping_file(tmp_path / "map.json", info)
    async with admin.begin() as conn:
        await conn.execute(
            sa.text(
                "ALTER TABLE release_migration_receipts ADD COLUMN unreviewed_receipt_state text"
            )
        )
    async with organisation_session(maker, PRIMAVERA_TEAM_ID) as db:
        before = await _snapshot(db, PRIMAVERA_TEAM_ID, KNOWN)
        with pytest.raises(ValidationError, match="Release receipt columns differ"):
            await replace_in_transaction(
                db,
                package,
                mappings,
                changes,
                expected_database=info["database"],
                mapping_sha256=mapping_hash,
            )
        await db.rollback()
        assert await _snapshot(db, PRIMAVERA_TEAM_ID, KNOWN) == before
