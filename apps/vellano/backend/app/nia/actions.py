from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Callable, Optional

from pydantic import BaseModel, Field

from app.permissions import (
    BOOKS_MUTATE,
    CATALOGUE_MUTATE,
    PO_RAISE,
    SALES_CUSTOMERS,
    SALES_DELIVERIES,
    SALES_LAYBYS,
    SALES_RETURNS,
    SETTINGS_MUTATE,
    STOCK_RECEIVE,
    STOCK_TRANSFER,
    TILL_SELL,
    USERS_MANAGE,
)
from app.schemas.account import AccountUpdate
from app.schemas.bank_import import BankApplyRuleRequest, BankImportMatchRequest, BankRecodeRequest
from app.schemas.bank_rule import BankRuleUpdate
from app.schemas.cost_audit import UnitCostCorrectionRequest
from app.schemas.customer_crm import CustomerCrmUpdate
from app.schemas.delivery import DeliveryComplete
from app.schemas.layby import LaybyPaymentCreate
from app.schemas.location import LocationUpdate
from app.schemas.location_bin import BinCreate, BinGridCreate, BinUpdate
from app.schemas.pick import PickComplete, PickConfirm, PickUpdate
from app.schemas.repeating_invoice import RepeatingInvoiceUpdate
from app.schemas.role import RoleUpdate
from app.schemas.sku import SkuUpdate
from app.schemas.sku_bom import SkuBomReplace
from app.schemas.stock_adjustment import StockAdjustmentLineCreate, StockAdjustmentLineUpdate
from app.schemas.stocktake import StocktakeLineCountUpdate, StocktakeLookupRequest
from app.schemas.transfer import TransferReceive
from app.schemas.user import UserUpdate
from app.schemas.vat201_period import Vat201PeriodReopen

SECRET_ARG_KEYS: frozenset[str] = frozenset({"password", "password_hash"})

_PERM_PHRASE: dict[str, str] = {
    CATALOGUE_MUTATE: "change the catalogue",
    STOCK_RECEIVE: "receive stock or change warehouse records",
    STOCK_TRANSFER: "create or dispatch transfers",
    TILL_SELL: "receive transfers",
    SALES_DELIVERIES: "manage picks or deliveries",
    SALES_CUSTOMERS: "change customers",
    USERS_MANAGE: "manage users",
    PO_RAISE: "change customer credit",
    SALES_RETURNS: "process returns",
    SALES_LAYBYS: "manage laybys",
    BOOKS_MUTATE: "change the books",
    SETTINGS_MUTATE: "change settings",
}


class NiaEmptyArgs(BaseModel):
    pass


class SkuUpdateArgs(SkuUpdate):
    sku_id: uuid.UUID


class SkuIdArgs(BaseModel):
    sku_id: uuid.UUID


class SkuBomReplaceArgs(SkuBomReplace):
    sku_id: uuid.UUID


class ProformaCreateArgs(BaseModel):
    supplier_id: uuid.UUID
    invoice_number: str = Field(min_length=1)
    invoice_date: datetime.date
    currency: Optional[str] = None


class ProformaIdArgs(BaseModel):
    proforma_id: uuid.UUID


class PurchaseOrderIdArgs(BaseModel):
    po_id: uuid.UUID


class LandPurchaseOrderArgs(BaseModel):
    po_id: uuid.UUID
    fx_to_zar: Decimal = Field(gt=0)
    factory_invoice_number: str = Field(min_length=1)
    factory_amount: Decimal
    factory_currency: Optional[str] = None
    freight_invoice_number: str = Field(min_length=1)
    freight_amount: Decimal
    freight_currency: str
    clearance_invoice_number: str = Field(min_length=1)
    clearance_amount: Decimal
    clearance_currency: str


class TransferIdArgs(BaseModel):
    transfer_id: uuid.UUID


class ReceiveTransferArgs(TransferReceive):
    transfer_id: uuid.UUID


class AdjustmentIdArgs(BaseModel):
    adjustment_id: uuid.UUID


class AddAdjustmentLineArgs(StockAdjustmentLineCreate):
    adjustment_id: uuid.UUID


class UpdateAdjustmentLineArgs(StockAdjustmentLineUpdate):
    adjustment_id: uuid.UUID
    line_id: uuid.UUID


class DeleteAdjustmentLineArgs(BaseModel):
    adjustment_id: uuid.UUID
    line_id: uuid.UUID


class StocktakeIdArgs(BaseModel):
    stocktake_id: uuid.UUID


class UpdateStocktakeLineArgs(StocktakeLineCountUpdate):
    stocktake_id: uuid.UUID
    line_id: uuid.UUID


class LookupStocktakeArgs(StocktakeLookupRequest):
    stocktake_id: uuid.UUID


class CorrectUnitCostArgs(UnitCostCorrectionRequest):
    sku_id: uuid.UUID


class LocationIdArgs(BaseModel):
    location_id: uuid.UUID


class LocationUpdateArgs(LocationUpdate):
    location_id: uuid.UUID


class CreateBinArgs(BinCreate):
    location_id: uuid.UUID


class GenerateBinGridArgs(BinGridCreate):
    location_id: uuid.UUID


class UpdateBinArgs(BinUpdate):
    location_id: uuid.UUID
    bin_id: uuid.UUID


class PickIdArgs(BaseModel):
    pick_id: uuid.UUID


class UpdatePickArgs(PickUpdate):
    pick_id: uuid.UUID


class ConfirmPickArgs(PickConfirm):
    pick_id: uuid.UUID


class CompletePickArgs(PickComplete):
    pick_id: uuid.UUID


class CustomerIdArgs(BaseModel):
    customer_id: uuid.UUID


class CustomerUpdateArgs(CustomerCrmUpdate):
    customer_id: uuid.UUID


class ReturnIdArgs(BaseModel):
    return_id: uuid.UUID


class LaybyIdArgs(BaseModel):
    layby_id: uuid.UUID


class AddLaybyPaymentArgs(LaybyPaymentCreate):
    layby_id: uuid.UUID


class DeliveryIdArgs(BaseModel):
    delivery_id: uuid.UUID


class CompleteDeliveryArgs(DeliveryComplete):
    delivery_id: uuid.UUID


class AccountIdArgs(BaseModel):
    account_id: uuid.UUID


class AccountUpdateArgs(AccountUpdate):
    account_id: uuid.UUID


class InvoiceIdArgs(BaseModel):
    invoice_id: uuid.UUID


class BillIdArgs(BaseModel):
    bill_id: uuid.UUID


class CreditNoteIdArgs(BaseModel):
    credit_note_id: uuid.UUID


class JournalIdArgs(BaseModel):
    journal_id: uuid.UUID


class RepeatingInvoiceIdArgs(BaseModel):
    schedule_id: uuid.UUID


class RepeatingInvoiceUpdateArgs(RepeatingInvoiceUpdate):
    schedule_id: uuid.UUID


class BankRuleIdArgs(BaseModel):
    rule_id: uuid.UUID


class BankRuleUpdateArgs(BankRuleUpdate):
    rule_id: uuid.UUID


class MatchBankLineArgs(BankImportMatchRequest):
    import_id: uuid.UUID
    line_id: uuid.UUID


class ApplyBankRuleArgs(BankApplyRuleRequest):
    import_id: uuid.UUID
    line_id: uuid.UUID


class RecodeBankLineArgs(BankRecodeRequest):
    import_id: uuid.UUID
    line_id: uuid.UUID


class PeriodIdArgs(BaseModel):
    period_id: uuid.UUID


class ReopenPeriodArgs(Vat201PeriodReopen):
    period_id: uuid.UUID


class UserIdArgs(BaseModel):
    user_id: uuid.UUID


class UserUpdateArgs(UserUpdate):
    user_id: uuid.UUID


class RoleIdArgs(BaseModel):
    role_id: uuid.UUID


class RoleUpdateArgs(RoleUpdate):
    role_id: uuid.UUID


class ListSkusArgs(BaseModel):
    category: Optional[str] = None


class ReportAsOfArgs(BaseModel):
    as_of: Optional[datetime.date] = None


class ReportRangeArgs(BaseModel):
    from_date: Optional[datetime.date] = None
    to_date: Optional[datetime.date] = None


@dataclass(frozen=True)
class NiaAction:
    id: str
    title: str
    permission: Optional[tuple[str, ...]]
    write: bool
    args_model: type[BaseModel]
    handler: Callable


def action_allowed(action: NiaAction, permissions: list[str]) -> bool:
    if action.permission is None:
        return True
    return any(key in permissions for key in action.permission)


def missing_permission_message(action: NiaAction, permissions: list[str]) -> str:
    keys = action.permission or ()
    missing = next((key for key in keys if key not in permissions), keys[0] if keys else "")
    phrase = _PERM_PHRASE.get(missing, action.title.lower())
    return f"Your role cannot {phrase} (missing {missing})."


def redact_mapping(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            if key in SECRET_ARG_KEYS:
                redacted[key] = "[redacted]"
            else:
                redacted[key] = redact_mapping(item)
        return redacted
    if isinstance(value, list):
        return [redact_mapping(item) for item in value]
    return value


def hitl_body(action: NiaAction, data: BaseModel) -> str:
    dumped = redact_mapping(data.model_dump(mode="json"))
    if not dumped:
        summary = action.title
    else:
        parts = [f"{key}={item}" for key, item in dumped.items()]
        summary = f"{action.title}: {', '.join(parts)}"
    if action.id == "delete_sku":
        summary += (
            " This permanently deletes the SKU. Confirm only if you intend to destroy"
            " this catalogue item."
        )
    return summary
