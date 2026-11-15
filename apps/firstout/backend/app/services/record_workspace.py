"""The record workspace seam: complete scoped queries and reviewed bulk actions."""

from __future__ import annotations

import uuid

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

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
)
from app.services.accounts import AccountService
from app.services.customers_crm import CustomersCrmService
from app.services.customer_credit import CREDIT_OVERRIDE_KEYS
from app.services.locations import LocationService
from app.services.permissions import PermissionService
from app.services.price_lists import PriceListService
from app.services.proformas import ProformaService
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

    async def rows(self, resource: str) -> list[BaseModel]:
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
        return await RepeatingInvoiceService(self.db).list()

    async def row(self, resource: str, record_id: uuid.UUID) -> BaseModel:
        """Reload just the reviewed record, through its original response mapping."""
        if resource == "customers":
            return await CustomersCrmService(self.db).get(record_id)
        if resource == "suppliers":
            return await SupplierService(self.db).get(record_id)
        if resource == "price-lists":
            return await PriceListService(self.db).get(record_id)
        if resource == "proformas":
            return await ProformaService(self.db).get(record_id)
        if resource == "repeating-invoices":
            return await RepeatingInvoiceService(self.db).get(record_id)
        if resource == "users":
            return await UserService(self.db).get(record_id)
        if resource == "accounts":
            return await AccountService(self.db).get(record_id)
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
        rows = await self.rows(resource)
        active = [row for row in rows if not archived(row, definition.archive_field)]
        past = [row for row in rows if archived(row, definition.archive_field)]
        candidates = (
            rows if query.lifecycle == "all" else past if query.lifecycle == "archived" else active
        )
        matching = filter_rows(candidates, query, definition.fields)
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
        return WorkspaceQueryResponse(
            items=page,
            total=len(matching),
            counts=WorkspaceCounts(active=len(active), archived=len(past)),
            revisions={str(row.id): revision(row) for row in page},
            selection_token=token,
            selection_ids=[row.id for row in matching] if token else [],
            selection_count=len(matching),
            bulk_available=bulk_available,
        )

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
        records = {str(row.id): row for row in await self.rows(resource)}
        eligible, blocked, expected = [], [], {}
        for record_id in ids:
            row = records.get(record_id)
            reason = "Record is no longer available" if row is None else None
            if row is not None:
                current_revision = revision(row)
                if revisions.get(record_id, current_revision) != current_revision:
                    reason = "Record changed since selection; refresh and review again"
                else:
                    reason = await self.eligibility(resource, body.action, row, len(ids), patch)
            if reason:
                blocked.append(
                    WorkspaceBlocked(
                        id=record_id,
                        label=label(row) if row else "Unavailable record",
                        reason=reason,
                    )
                )
            else:
                eligible.append(WorkspaceEligible(id=row.id, label=label(row)))
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
