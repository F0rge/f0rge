"""The record workspace seam: complete scoped queries and reviewed bulk actions."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

import datetime

from app.crud.purchase_order import LocationStockCRUD
from app.crud.sku_stock_figures import on_order_by_sku_id
from app.exceptions import ForbiddenError
from app.schemas.location import LocationResponse
from app.schemas.record_workspace import (
    WorkspaceBlocked,
    WorkspaceCounts,
    WorkspaceEligible,
    WorkspacePreflight,
    WorkspacePreflightResponse,
    WorkspaceQuery,
    WorkspaceQueryResponse,
    WorkspaceSkuRow,
    WorkspaceStockLocation,
)
from app.services.accounts import AccountService
from app.services.bills import BillService
from app.services.customers_crm import CustomersCrmService
from app.services.customer_credit import CREDIT_OVERRIDE_KEYS
from app.services.invoices import InvoiceService
from app.services.locations import LocationService
from app.services.payments import PaymentService
from app.services.permissions import PermissionService
from app.services.price_lists import PriceListService
from app.services.proformas import ProformaService
from app.services.quotes import QuotesService
from app.services.record_workspace_actions import blocked_reason, validate_patch
from app.services.record_workspace_filters import archived, filter_rows, label, revision
from app.services.record_workspace_registry import DEFINITIONS
from app.services.record_workspace_tokens import (
    issue_token,
    read_token,
    require_signing_key,
    signing_key,
)
from app.services.repeating_invoices import RepeatingInvoiceService
from app.services.roles import RoleService
from app.services.suppliers import SupplierService
from app.services.users import UserService
from app.services.skus import SkuService
from app.services.sku_archive import SkuArchiveService
from app.services.stock_availability import StockAvailability
from f0rge_core.exceptions import NotFoundError, ValidationError


class RecordWorkspaceService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.permissions = PermissionService(db)

    async def require_access(self, resource: str, actor: uuid.UUID, action="", patch=None):
        definition = DEFINITIONS[resource]
        key = definition.permission if action else definition.read_permission
        if resource == "customers" and action == "edit":
            await CustomersCrmService(self.db)._assert_patch_permissions(actor, set(patch or {}))
        elif key and not await self.permissions.has_permission(actor, key):
            raise ForbiddenError("You do not have permission to perform this action")
        if action and action not in definition.actions:
            raise ValidationError("This action is not supported for these records")
        return definition

    async def rows(self, resource: str, actor: Optional[uuid.UUID] = None) -> list[BaseModel]:
        if resource == "skus":
            return await SkuService(self.db).list(user_id=actor, lifecycle="all")
        if resource == "customers":
            service = CustomersCrmService(self.db)
            return await service.list() + await service.list(archived=True)
        if resource == "suppliers":
            service = SupplierService(self.db)
            return await service.list() + await service.list(archived=True)
        if resource == "price-lists":
            return await PriceListService(self.db).list(archived=None)
        if resource == "proformas":
            return await ProformaService(self.db).list(archived=None)
        if resource == "quotes":
            return await QuotesService(self.db).list_all()
        if resource == "locations":
            return [
                LocationResponse.model_validate(row)
                for row in await LocationService(self.db).list()
            ]
        if resource == "users":
            return await UserService(self.db).list()
        if resource == "roles":
            return await RoleService(self.db).list()
        if resource == "accounts":
            return await AccountService(self.db).list()
        if resource == "payments":
            return await PaymentService(self.db).list_all()
        if resource == "bills":
            return await BillService(self.db).list_all()
        if resource == "invoices":
            return await InvoiceService(self.db).list_all()
        return await RepeatingInvoiceService(self.db).list()

    async def row(
        self, resource: str, record_id: uuid.UUID, actor: Optional[uuid.UUID] = None
    ) -> BaseModel:
        """Reload just the reviewed record, through its original response mapping."""
        if resource == "skus":
            return await SkuService(self.db).get(record_id, actor)
        if resource == "customers":
            return await CustomersCrmService(self.db).get(record_id)
        if resource == "suppliers":
            return await SupplierService(self.db).get(record_id)
        if resource == "price-lists":
            return await PriceListService(self.db).get(record_id)
        if resource == "proformas":
            return await ProformaService(self.db).get(record_id)
        if resource == "quotes":
            return await QuotesService(self.db).get_item(record_id)
        if resource == "repeating-invoices":
            return await RepeatingInvoiceService(self.db).get(record_id)
        if resource == "users":
            return await UserService(self.db).get(record_id)
        if resource == "accounts":
            return await AccountService(self.db).get(record_id)
        if resource == "bills":
            return await BillService(self.db).get_list_item(record_id)
        if resource == "invoices":
            return await InvoiceService(self.db).get_list_item(record_id)
        service = RoleService(self.db) if resource == "roles" else LocationService(self.db)
        record = await service.crud.get_by_id(record_id)
        if record is None:
            raise NotFoundError("Record not found")
        return (
            service._to_response(record)
            if resource == "roles"
            else LocationResponse.model_validate(record)
        )

    async def query(
        self, resource: str, query: WorkspaceQuery, actor: uuid.UUID
    ) -> WorkspaceQueryResponse:
        definition = await self.require_access(resource, actor)
        requested_fields = {condition.field for condition in query.filters}
        if query.sort:
            requested_fields.add(query.sort.field)
        if (
            resource == "customers"
            and "on_hold" in requested_fields
            and not await self.permissions.has_any(actor, CREDIT_OVERRIDE_KEYS)
        ):
            raise ForbiddenError("Credit fields require additional permission")
        rows = await self.rows(resource, actor)
        active = [row for row in rows if not archived(row, definition.archive_field)]
        past = [row for row in rows if archived(row, definition.archive_field)]
        candidates = (
            rows if query.lifecycle == "all" else past if query.lifecycle == "archived" else active
        )
        stock_locations = None
        if resource == "skus" and "on_hand" in requested_fields:
            stock_locations = await LocationStockCRUD(self.db).on_hand_locations_by_sku_id()
        on_hand = (
            {
                sku_id: sum((qty for _, _, qty in locations), Decimal(0))
                for sku_id, locations in stock_locations.items()
            }
            if stock_locations is not None
            else None
        )
        derived: Optional[dict[str, dict]] = {"on_hand": on_hand} if on_hand is not None else None
        if resource == "skus":
            derived = {**(derived or {}), **_sku_material_values(candidates)}
            if "available" in requested_fields:
                derived["available"] = await _available(self.db, [row.id for row in candidates])
        matching = filter_rows(candidates, query, definition.fields, derived)
        page = matching[query.offset : query.offset + query.limit]
        token = None
        bulk_available = signing_key() is not None
        if len(matching) <= 500 and bulk_available:
            token = issue_token(
                "selection",
                resource,
                actor,
                {
                    "ids": [str(row.id) for row in matching],
                    "revisions": {str(row.id): revision(row) for row in matching},
                },
            )
        # Stock is a read projection. Bulk preflight/execute still compare original SKU revisions.
        items = page
        if resource == "skus":
            items = await self._add_catalogue_stock(page, stock_locations)
        return WorkspaceQueryResponse(
            items=items,
            total=len(matching),
            counts=WorkspaceCounts(active=len(active), archived=len(past)),
            revisions={str(row.id): revision(row) for row in page},
            selection_token=token,
            selection_ids=[row.id for row in matching] if token else [],
            selection_count=len(matching),
            bulk_available=bulk_available,
        )

    async def _add_catalogue_stock(
        self,
        page: list[BaseModel],
        locations_by_id: Optional[dict[uuid.UUID, list[tuple[uuid.UUID, str, Decimal]]]],
    ) -> list[BaseModel]:
        sku_ids = [row.id for row in page]
        if locations_by_id is None:
            locations_by_id = await LocationStockCRUD(self.db).on_hand_locations_by_sku_id(sku_ids)
        on_order_by_id = await on_order_by_sku_id(self.db, sku_ids)
        available_by_id = await _available(self.db, sku_ids)
        items: list[BaseModel] = []
        for sku in page:
            locations = locations_by_id.get(sku.id, [])
            items.append(
                WorkspaceSkuRow(
                    **sku.model_dump(),
                    on_hand=sum((qty for _, _, qty in locations), Decimal(0)),
                    on_order=on_order_by_id.get(sku.id, Decimal(0)),
                    available=available_by_id[sku.id],
                    stock_locations=[
                        WorkspaceStockLocation(location_id=id_, location_name=name, on_hand=qty)
                        for id_, name, qty in locations
                    ],
                )
            )
        return items

    async def preflight(
        self, resource: str, body: WorkspacePreflight, actor: uuid.UUID
    ) -> WorkspacePreflightResponse:
        definition = await self.require_access(resource, actor, body.action, body.patch)
        await self.require_access(resource, actor)
        require_signing_key()
        patch = (
            validate_patch(resource, body.patch, definition.editable)
            if body.action == "edit"
            else {}
        )
        ids = [str(value) for value in dict.fromkeys(body.ids)]
        revisions = body.revisions
        if body.selection_token:
            selection = read_token(body.selection_token, "selection", resource, actor)
            excluded = {str(value) for value in body.excluded_ids}
            ids = [value for value in selection["ids"] if value not in excluded]
            revisions = selection["revisions"]
        if not ids or len(ids) > 500:
            raise ValidationError(
                "Choose between 1 and 500 records; refine filters for a larger result"
            )
        if len(str(patch)) > 16000:
            raise ValidationError("The bulk changes are too large")
        records = {str(row.id): row for row in await self.rows(resource, actor)}
        eligible, blocked, expected, dependencies = [], [], {}, {}
        for record_id in ids:
            row = records.get(record_id)
            reason = "Record is no longer available" if row is None else None
            if row is not None:
                current_revision = revision(row)
                if revisions.get(record_id, current_revision) != current_revision:
                    reason = "Record changed since selection; refresh and review again"
                else:
                    if resource == "skus":
                        past = archived(row, definition.archive_field)
                        if (body.action == "archive") == past:
                            reason = (
                                "This record is already inactive"
                                if past
                                else "This record is already active"
                            )
                    else:
                        reason = await self.eligibility(resource, body.action, row, len(ids), patch)
            impact = (
                await SkuArchiveService(self.db).impact(row.id, body.action)
                if resource == "skus" and row is not None
                else None
            )
            if impact and not reason:
                reason = impact.reason
            if reason:
                blocked.append(
                    WorkspaceBlocked(
                        id=record_id,
                        label=label(row) if row else "Unavailable record",
                        reason=reason,
                        warnings=impact.warnings if impact else [],
                        dependencies=impact.dependencies if impact else [],
                    )
                )
            else:
                eligible.append(
                    WorkspaceEligible(
                        id=row.id,
                        label=label(row),
                        warnings=impact.warnings if impact else [],
                    )
                )
                if impact:
                    dependencies[record_id] = impact.fingerprint
                expected[record_id] = revision(row)
        token = issue_token(
            "preflight",
            resource,
            actor,
            {
                "action": body.action,
                "patch": patch,
                "ids": [str(row.id) for row in eligible],
                "revisions": expected,
                "dependencies": dependencies,
            },
        )
        return WorkspacePreflightResponse(
            preflight_token=token,
            eligible=eligible,
            blocked=blocked,
            eligible_count=len(eligible),
            blocked_count=len(blocked),
        )

    async def eligibility(self, resource: str, action: str, row, count: int, patch: dict):
        definition = DEFINITIONS[resource]
        past = archived(row, definition.archive_field)
        if action in {"archive", "disable", "pause"} and past:
            return "This record is already inactive"
        if action in {"restore", "enable", "resume"} and not past:
            return "This record is already active"
        return await blocked_reason(self.db, resource, action, row, count, patch)


def _sku_material_values(rows: list[BaseModel]) -> dict[str, dict]:
    """Filter values read from the SKU's material summaries, for every row."""
    main: dict = {}
    family: dict = {}
    every: dict = {}
    for row in rows:
        material = getattr(row, "main_material", None)
        others = getattr(row, "other_materials", [])
        main[row.id] = material.name if material is not None else None
        family[row.id] = material.family if material is not None else None
        every[row.id] = [item.name for item in ([material] if material else []) + others]
    return {"main_material": main, "material_family": family, "material": every}


async def _available(db: AsyncSession, sku_ids: list[uuid.UUID]) -> dict[uuid.UUID, Decimal]:
    now = datetime.datetime.now(datetime.timezone.utc)
    figures = await StockAvailability(db).company_available(sku_ids, now)
    return {sku_id: max(Decimal(0), figures.get(sku_id, Decimal(0))) for sku_id in sku_ids}
