"""Reviewed Primavera-only replacement; dry-run rollback is the default.

No provider operations, credential discovery, object deletion or background jobs.
Commit requires the exact reviewed plan plus independently prepared backup evidence.
"""

from __future__ import annotations

import argparse
import asyncio
import datetime
import hashlib
import json
import sys
import uuid
from pathlib import Path
from typing import Optional

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, array
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import Base, TenantSession
from app.models.team import Team
from app.models.sku import Sku
from app.models.location import Location
from app.crud.cin7_import_run import Cin7ImportRunCRUD
from app.models.cin7_import_run import Cin7ImportRun
from app.runtime_database import verify_runtime_role
from app.services.cin7_import.prepared import (
    BinMapping,
    PreparedLoader,
    PreparedPackage,
    file_sha256,
)
from f0rge_core.exceptions import ValidationError
from f0rge_db.organisation import tenant_id_ctx

PRIMAVERA_TEAM_ID = uuid.UUID("54493247-36a3-4ed6-a3ff-5bd35cc4f522")
SCHEMA_REVISION = "087_cin7_archive_provenance"
PRESERVE = frozenset(
    (
        "teams",
        "users",
        "memberships",
        "roles",
        "role_permissions",
        "team_settings",
        "tenant_invitations",
        "tenant_provisioning_attempts",
        "password_reset_tokens",
        "clerk_webhook_events",
        "portal_access",
        "portal_invitations",
        "customer_portal_users",
        "cin7_import_runs",
        "accounts",
        "tax_rules",
        "payment_terms",
        "category_account_maps",
        "books_periods",
        "bank_rules",
        "document_sequences",
        "locations",
        "location_bins",
    )
)
REQUIRE_EMPTY = frozenset(
    (
        "portal_access",
        "portal_invitations",
        "customer_portal_users",
        "ops_commerce_orders",
        "ops_commerce_refunds",
        "ops_commerce_refund_events",
        "ops_commerce_fulfillment_events",
        "ops_commerce_acknowledgements",
    )
)
DELETE_BUSINESS = frozenset(
    (
        "archive_credit_notes",
        "archive_credit_note_lines",
        "bank_imports",
        "bank_import_lines",
        "bank_import_line_allocations",
        "bills",
        "bill_lines",
        "tax_invoices",
        "invoice_lines",
        "books_events",
        "comms_messages",
        "credit_notes",
        "customers",
        "customer_addresses",
        "customer_contacts",
        "suppliers",
        "supplier_addresses",
        "supplier_contacts",
        "deliveries",
        "delivery_lines",
        "sku_stock",
        "location_stock",
        "journal_entries",
        "journal_lines",
        "laybys",
        "layby_lines",
        "layby_payments",
        "bin_stock",
        "payments",
        "payment_reminder_sends",
        "picks",
        "pick_lines",
        "pick_allocations",
        "price_lists",
        "price_list_items",
        "product_groups",
        "product_group_variants",
        "proformas",
        "purchase_orders",
        "po_lines",
        "landing_bills",
        "quotes",
        "quote_lines",
        "repeating_invoices",
        "repeating_invoice_lines",
        "sales_orders",
        "sales_order_lines",
        "sales_order_payments",
        "skus",
        "sku_bom_lines",
        "sku_supplier_prices",
        "stock_adjustments",
        "stock_adjustment_lines",
        "stock_returns",
        "stock_return_lines",
        "stocktakes",
        "stocktake_lines",
        "transfers",
        "transfer_lines",
        "unit_cost_audit",
        "vat201_periods",
        "vat201_period_events",
    )
)
KNOWN = PRESERVE | DELETE_BUSINESS | REQUIRE_EMPTY


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def read_mapping(path: Path, expected_hash: str) -> tuple[list[BinMapping], list[dict]]:
    if file_sha256(path) != expected_hash:
        raise ValidationError("Bin mapping hash does not match the reviewed mapping")
    value = json.loads(path.read_text())
    if value.get("format") != "firstout-source-bin-map-v1" or value.get("target_team_id") != str(
        PRIMAVERA_TEAM_ID
    ):
        raise ValidationError("Bin map format/target differs from the approved Primavera mapping")
    mappings = [
        BinMapping(
            source_location=item["source_location"],
            source_bin=item["source_bin"],
            location_id=uuid.UUID(item["target_location_id"]),
            bin_id=uuid.UUID(item["target_bin_id"]),
            target_location_name=item["target_location_name"],
            target_bin_code=item["target_bin_code"],
        )
        for item in value["mappings"]
    ]
    changes = [
        dict(
            location_id=item["id"],
            expected_name=item["expected_name"],
            name=item["name"],
            expected_is_archived=None,
            is_archived=item["is_archived"],
        )
        for item in value.get("location_updates", [])
    ]
    changes.extend(
        dict(
            location_id=location_id,
            expected_name=None,
            name=None,
            expected_is_archived=None,
            is_archived=True,
        )
        for location_id in value.get("archive_location_ids", [])
    )
    allowed = {"location_id", "expected_name", "name", "expected_is_archived", "is_archived"}
    if any(set(item) != allowed for item in changes) or len(
        {item["location_id"] for item in changes}
    ) != len(changes):
        raise ValidationError("Location changes require exact reviewed before/after fields")
    return mappings, changes


def _scope(table: sa.Table, team_id: uuid.UUID):
    if "team_id" in table.c:
        return table.c.team_id == team_id
    if "organisation_id" in table.c:
        return table.c.organisation_id == team_id
    return sa.true()


async def _snapshot(db: AsyncSession, team_id: uuid.UUID, names, *, location_changes=()) -> dict:
    tables = {}
    mutable_locations = {str(item["location_id"]): item for item in location_changes}
    for name in sorted(names):
        table = Base.metadata.tables[name]
        predicate = _scope(table, team_id)
        # Raw customer data, settings and tokens never cross this read boundary.
        # Built-in MD5 is an integrity fingerprint, not an authentication primitive.
        value = sa.func.to_jsonb(table.table_valued(), type_=JSONB)
        if name == "locations" and mutable_locations:
            projections = []
            for location_id, change in mutable_locations.items():
                fields = ["is_archived", "archived_at", "updated_at"]
                if change["name"] is not None:
                    fields.append("name")
                projections.append(
                    (
                        table.c.id == uuid.UUID(location_id),
                        value.op("-")(array(fields, type_=sa.Text)),
                    )
                )
            value = sa.case(*projections, else_=value)
        stmt = sa.select(sa.func.md5(value.cast(sa.Text))).select_from(table).where(predicate)
        hashes = list(await db.scalars(stmt))
        tables[name] = {"count": len(hashes), "sha256": _digest(sorted(hashes))}
    return {"tables": tables, "sha256": _digest(tables)}


async def _other_organisations(db: AsyncSession, target: uuid.UUID) -> dict:
    # Audit through this transaction so even accidental uncommitted writes are
    # visible. Only raw read scopes switch; session ownership/context stay fixed.
    await db.flush()
    teams = list(await db.scalars(sa.select(Team.id).where(Team.id != target)))
    original = await db.scalar(sa.text("SELECT current_setting('app.tenant_id', true)"))
    result = {}
    try:
        for team_id in sorted(teams, key=str):
            await db.execute(
                sa.text("SELECT set_config('app.tenant_id', :id, true)"), {"id": str(team_id)}
            )
            for name in REQUIRE_EMPTY:
                table = Base.metadata.tables[name]
                if "company_id" in table.c and await db.scalar(
                    sa.select(sa.func.count())
                    .select_from(table)
                    .where(table.c.team_id == team_id, table.c.company_id == target)
                ):
                    raise ValidationError(
                        "Foreign-organisation commerce rows bind the Primavera company"
                    )
            result[str(team_id)] = (await _snapshot(db, team_id, KNOWN))["sha256"]
    finally:
        await db.execute(
            sa.text("SELECT set_config('app.tenant_id', :id, true)"), {"id": original or ""}
        )
    return result


async def _preflight(db: AsyncSession, expected_database: str) -> Team:
    if tenant_id_ctx.get() != PRIMAVERA_TEAM_ID:
        raise ValidationError("Replacement is restricted to the verified Primavera team UUID")
    await verify_runtime_role(db)
    database = await db.scalar(sa.text("SELECT current_database()"))
    if database != expected_database:
        raise ValidationError("Database identity does not match the reviewed target")
    revision = await db.scalar(sa.text("SELECT version_num FROM alembic_version"))
    if revision != SCHEMA_REVISION:
        raise ValidationError("Replacement requires the exact reviewed schema revision087")
    team = await db.scalar(sa.select(Team).where(Team.id == PRIMAVERA_TEAM_ID))
    if (
        team is None
        or team.slug != "firstout"
        or team.name != "Primavera"
        or team.status != "maintenance"
    ):
        raise ValidationError("Verified Primavera identity and maintenance fence are required")
    live = set(
        await db.scalars(sa.text("SELECT tablename FROM pg_tables WHERE schemaname='public'"))
    )
    if live != KNOWN | {"alembic_version"} or set(Base.metadata.tables) != KNOWN:
        raise ValidationError(
            "Live tables differ from the explicitly reviewed replacement inventory"
        )
    if not await Cin7ImportRunCRUD(db).try_lock():
        raise ValidationError("Another Cin7 transaction holds the target import lock")
    if await db.scalar(
        sa.select(Cin7ImportRun.id)
        .where(Cin7ImportRun.team_id == team.id, Cin7ImportRun.active_lock.is_(True))
        .limit(1)
    ):
        raise ValidationError("An active Cin7 import job prevents replacement")
    for name in REQUIRE_EMPTY:
        table = Base.metadata.tables[name]
        if await db.scalar(
            sa.select(sa.func.count()).select_from(table).where(_scope(table, team.id))
        ):
            raise ValidationError("Unexpected portal or commerce bindings prevent safe replacement")
    return team


async def replace_in_transaction(
    db: AsyncSession,
    package: PreparedPackage,
    mappings: list[BinMapping],
    location_changes: list[dict],
    *,
    expected_database: str,
    mapping_sha256: str,
    expected_before: Optional[str] = None,
) -> dict:
    """No commit/rollback: callers must keep this entire operation atomic."""
    team = await _preflight(db, expected_database)
    before = await _snapshot(db, team.id, KNOWN)
    if expected_before is not None and before["sha256"] != expected_before:
        raise ValidationError("Target data changed after the reviewed dry run/backup")
    protected = await _snapshot(db, team.id, PRESERVE, location_changes=location_changes)
    other = await _other_organisations(db, team.id)
    source_codes = {row["ProductCode"] for row in package.rows["data/InventoryList_cleaned.csv"]}
    stable = {}
    for sku in await db.scalars(sa.select(Sku).where(Sku.team_id == team.id)):
        if sku.storefront_published and sku.our_ref not in source_codes:
            raise ValidationError(
                "A published commerce SKU is absent from the reviewed retained catalogue"
            )
        if sku.our_ref in source_codes:
            stable[sku.our_ref] = (str(sku.id), sku.storefront_published, sku.photo_storage_key)
    checked_locations = []
    for change in location_changes:
        location = await db.scalar(
            sa.select(Location).where(
                Location.id == uuid.UUID(change["location_id"]), Location.team_id == team.id
            )
        )
        if (
            location is None
            or (change["expected_name"] is not None and location.name != change["expected_name"])
            or (
                change["expected_is_archived"] is not None
                and location.is_archived is not change["expected_is_archived"]
            )
        ):
            raise ValidationError(
                "Location state differs from the explicitly approved rename/archive plan"
            )
        checked_locations.append((location, change))
    # Release legacy active-name uniqueness before activating approved familiar names.
    for location, change in checked_locations:
        if change["is_archived"]:
            location.is_archived = True
            location.archived_at = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    await db.flush()
    for location, change in checked_locations:
        if change["name"] is not None:
            location.name = change["name"]
        location.is_archived = change["is_archived"]
        if not location.is_archived:
            location.archived_at = None
    await db.flush()
    deleted = {}
    for table in reversed(Base.metadata.sorted_tables):
        if table.name not in DELETE_BUSINESS:
            continue
        if "team_id" not in table.c:
            raise ValidationError("A business table lacks its reviewed tenant predicate")
        clause = table.c.team_id == team.id
        if table.name == "skus":
            clause = sa.and_(clause, table.c.our_ref.not_in(source_codes))
        result = await db.execute(sa.delete(table).where(clause))
        deleted[table.name] = result.rowcount
    db.expunge_all()
    result = await PreparedLoader(db, package, mappings).run()
    retained = {
        sku.our_ref: (str(sku.id), sku.storefront_published, sku.photo_storage_key)
        for sku in await db.scalars(sa.select(Sku).where(Sku.team_id == PRIMAVERA_TEAM_ID))
    }
    if any(retained.get(code) != identity for code, identity in stable.items()):
        raise ValidationError("Retained product UUID/publication/photo identity changed")
    after_protected = await _snapshot(
        db, PRIMAVERA_TEAM_ID, PRESERVE, location_changes=location_changes
    )
    if after_protected != protected or await _other_organisations(db, PRIMAVERA_TEAM_ID) != other:
        raise ValidationError("Protected or other-organisation data changed during replacement")
    return {
        "format": "firstout-primavera-replacement-v1",
        "team_id": str(PRIMAVERA_TEAM_ID),
        "database": expected_database,
        "schema_revision": SCHEMA_REVISION,
        "manifest_sha256": package.manifest_sha256,
        "mapping_sha256": mapping_sha256,
        "before_sha256": before["sha256"],
        "protected_sha256": protected["sha256"],
        "other_organisations": other,
        "deleted": deleted,
        "retained_sku_ids": len(stable),
        "location_changes": location_changes,
        "load": result,
    }


def _read_reviewed(path: Path, digest: str) -> dict:
    if file_sha256(path) != digest:
        raise ValidationError("Reviewed evidence file hash differs")
    return json.loads(path.read_text())


def _commit_evidence(args, package: PreparedPackage) -> dict:
    required = (
        args.reviewed_plan,
        args.reviewed_plan_sha256,
        args.backup_evidence,
        args.backup_evidence_sha256,
    )
    if not all(required):
        raise ValidationError(
            "Commit requires reviewed-plan and backup-evidence files with their exact hashes"
        )
    plan = _read_reviewed(args.reviewed_plan, args.reviewed_plan_sha256)
    evidence = _read_reviewed(args.backup_evidence, args.backup_evidence_sha256)
    if plan.get("committed") is not False or plan.get("dry_run_rolled_back") is not True:
        raise ValidationError("Commit requires a successfully rolled-back reviewed dry run")
    for key, value in (
        ("team_id", str(PRIMAVERA_TEAM_ID)),
        ("database", args.expected_database),
        ("manifest_sha256", package.manifest_sha256),
        ("mapping_sha256", args.mapping_sha256),
        ("schema_revision", SCHEMA_REVISION),
    ):
        if plan.get(key) != value:
            raise ValidationError("Reviewed dry-run target/package/schema/mapping differs")
    if (
        evidence.get("team_id") != str(PRIMAVERA_TEAM_ID)
        or evidence.get("database") != args.expected_database
        or evidence.get("before_sha256") != plan.get("before_sha256")
    ):
        raise ValidationError("Backup evidence is not bound to this target/baseline")
    if (
        evidence.get("restore_verified") is not True
        or evidence.get("writes_drained") is not True
        or not evidence.get("provider_project_id")
        or not evidence.get("provider_service_id")
    ):
        raise ValidationError("Verified restore/provider identity/write-drain evidence is required")
    backup = Path(evidence["backup_path"])
    if backup.stat().st_size == 0 or file_sha256(backup) != evidence.get("backup_sha256"):
        raise ValidationError("Recovery backup bytes do not match their verified checksum")
    return plan


async def _run(args) -> dict:
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from app.database import engine
    from f0rge_db.organisation import organisation_session

    if args.team_id != PRIMAVERA_TEAM_ID:
        raise ValidationError("Explicit team UUID does not match the authorized Primavera target")
    package = PreparedPackage.read(args.package, args.manifest_sha256)
    mappings, changes = read_mapping(args.bin_map, args.mapping_sha256)
    reviewed = _commit_evidence(args, package) if args.commit else None
    maker = async_sessionmaker(
        engine.execution_options(isolation_level="REPEATABLE READ"),
        expire_on_commit=False,
        sync_session_class=TenantSession,
    )
    async with organisation_session(maker, PRIMAVERA_TEAM_ID) as db:
        try:
            result = await replace_in_transaction(
                db,
                package,
                mappings,
                changes,
                expected_database=args.expected_database,
                mapping_sha256=args.mapping_sha256,
                expected_before=reviewed["before_sha256"] if reviewed else None,
            )
            if reviewed:
                for key in (
                    "protected_sha256",
                    "other_organisations",
                    "deleted",
                    "retained_sku_ids",
                    "load",
                    "location_changes",
                ):
                    if result[key] != reviewed[key]:
                        raise ValidationError(
                            "Commit outcome differs from the reviewed dry-run plan"
                        )
                await db.commit()
            else:
                await db.rollback()
            result.update(committed=bool(reviewed), dry_run_rolled_back=not bool(reviewed))
            return result
        except BaseException:
            await db.rollback()
            raise


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--team-id", type=uuid.UUID, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--bin-map", type=Path, required=True)
    parser.add_argument("--mapping-sha256", required=True)
    parser.add_argument("--expected-database", required=True)
    parser.add_argument("--commit", action="store_true")
    parser.add_argument("--reviewed-plan", type=Path)
    parser.add_argument("--reviewed-plan-sha256")
    parser.add_argument("--backup-evidence", type=Path)
    parser.add_argument("--backup-evidence-sha256")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(asyncio.run(_run(args)), indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        reason = exc.detail if isinstance(exc, ValidationError) else type(exc).__name__
        print(f"Primavera replacement refused: {reason}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
