from __future__ import annotations

import uuid
from typing import Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from app.schemas.account import AccountResponse
from app.schemas.customer_crm import CustomerCrmResponse
from app.schemas.location import LocationResponse
from app.schemas.price_list import PriceListResponse
from app.schemas.proforma import ProformaResponse
from app.schemas.repeating_invoice import RepeatingInvoiceResponse
from app.schemas.role import RoleResponse
from app.schemas.supplier import SupplierResponse
from app.schemas.user import UserResponse

WorkspaceResource = Literal[
    "customers",
    "suppliers",
    "price-lists",
    "locations",
    "users",
    "roles",
    "accounts",
    "repeating-invoices",
    "proformas",
]
WorkspaceAction = Literal[
    "edit",
    "archive",
    "restore",
    "delete",
    "disable",
    "enable",
    "pause",
    "resume",
]
WorkspaceRow = Union[
    CustomerCrmResponse,
    SupplierResponse,
    PriceListResponse,
    LocationResponse,
    UserResponse,
    RoleResponse,
    AccountResponse,
    RepeatingInvoiceResponse,
    ProformaResponse,
]


class WorkspaceFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: str = Field(min_length=1, max_length=64)
    operator: Literal["eq", "ne", "contains", "gt", "gte", "lt", "lte", "empty", "not_empty"]
    value: Union[str, int, float, bool, None] = None


class WorkspaceSort(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: str = Field(min_length=1, max_length=64)
    direction: Literal["asc", "desc"] = "asc"


class WorkspaceQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    q: str = Field(default="", max_length=256)
    lifecycle: Literal["active", "archived", "all"] = "active"
    match: Literal["all", "any"] = "all"
    filters: list[WorkspaceFilter] = Field(default_factory=list, max_length=20)
    sort: Optional[WorkspaceSort] = None
    limit: int = Field(default=25, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class WorkspaceCounts(BaseModel):
    active: int
    archived: int


class WorkspaceQueryResponse(BaseModel):
    items: list[WorkspaceRow]
    total: int
    counts: WorkspaceCounts
    revisions: dict[str, str]
    selection_token: Optional[str]
    selection_ids: list[uuid.UUID]
    selection_count: int
    bulk_available: bool


class WorkspacePreflight(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: WorkspaceAction
    ids: list[uuid.UUID] = Field(default_factory=list, max_length=500)
    selection_token: Optional[str] = Field(default=None, max_length=131072)
    excluded_ids: list[uuid.UUID] = Field(default_factory=list, max_length=500)
    revisions: dict[str, str] = Field(default_factory=dict)
    patch: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def selection_is_unambiguous(self):
        if bool(self.ids) == bool(self.selection_token):
            raise ValueError("Choose explicit record IDs or an all-matching selection")
        if self.excluded_ids and not self.selection_token:
            raise ValueError("Exclusions require an all-matching selection")
        if self.action != "edit" and self.patch:
            raise ValueError("Only editing accepts field changes")
        if self.action == "edit" and not self.patch:
            raise ValueError("Choose at least one field to change")
        return self


class WorkspaceEligible(BaseModel):
    id: uuid.UUID
    label: str


class WorkspaceBlocked(WorkspaceEligible):
    reason: str


class WorkspacePreflightResponse(BaseModel):
    preflight_token: str
    eligible: list[WorkspaceEligible]
    blocked: list[WorkspaceBlocked]
    eligible_count: int
    blocked_count: int


class WorkspaceExecute(BaseModel):
    model_config = ConfigDict(extra="forbid")
    preflight_token: str = Field(min_length=1, max_length=131072)
    request_id: uuid.UUID


class WorkspaceExecuteResponse(BaseModel):
    request_id: uuid.UUID
    succeeded: list[uuid.UUID]
    failed: list[WorkspaceBlocked]
    replayed: bool
