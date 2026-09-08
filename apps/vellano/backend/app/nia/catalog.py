from __future__ import annotations

import datetime
from typing import Any

from app.nia.actions import (
    AccountUpdateArgs,
    AddAdjustmentLineArgs,
    AddLaybyPaymentArgs,
    AdjustmentIdArgs,
    ApplyBankRuleArgs,
    BankRuleIdArgs,
    BankRuleUpdateArgs,
    BillIdArgs,
    CompleteDeliveryArgs,
    CompletePickArgs,
    ConfirmPickArgs,
    CorrectUnitCostArgs,
    CreateBinArgs,
    CreditNoteIdArgs,
    CustomerIdArgs,
    CustomerUpdateArgs,
    DeleteAdjustmentLineArgs,
    DeliveryIdArgs,
    GenerateBinGridArgs,
    InvoiceIdArgs,
    JournalIdArgs,
    LandPurchaseOrderArgs,
    LaybyIdArgs,
    ListSkusArgs,
    LocationIdArgs,
    LocationUpdateArgs,
    LookupStocktakeArgs,
    MatchBankLineArgs,
    NiaAction,
    NiaEmptyArgs,
    PeriodIdArgs,
    PickIdArgs,
    ProformaCreateArgs,
    ProformaIdArgs,
    PurchaseOrderIdArgs,
    ReceiveTransferArgs,
    RecodeBankLineArgs,
    ReopenPeriodArgs,
    RepeatingInvoiceIdArgs,
    RepeatingInvoiceUpdateArgs,
    ReportAsOfArgs,
    ReportRangeArgs,
    ReturnIdArgs,
    RoleIdArgs,
    RoleUpdateArgs,
    SkuBomReplaceArgs,
    SkuIdArgs,
    SkuUpdateArgs,
    StocktakeIdArgs,
    TransferIdArgs,
    UpdateAdjustmentLineArgs,
    UpdateBinArgs,
    UpdatePickArgs,
    UpdateStocktakeLineArgs,
    UserUpdateArgs,
)
from app.nia.agent import NiaDeps
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
from app.schemas.account import AccountCreate
from app.schemas.bank_rule import BankRuleCreate
from app.schemas.bill import BillCreate
from app.schemas.category_account_map import CategoryAccountMapUpsert
from app.schemas.contact import ContactCreate
from app.schemas.credit_note import CreditNoteCreate
from app.schemas.customer_crm import CustomerCrmCreate
from app.schemas.delivery import DeliveryCreate
from app.schemas.invoice import InvoiceCreate
from app.schemas.journal import JournalCreate
from app.schemas.layby import LaybyCreate
from app.schemas.location import LocationCreate, LocationResponse
from app.schemas.payment import PaymentCreate
from app.schemas.pick import PickCreate, PickPreviewRequest
from app.schemas.purchase_order import PurchaseOrderCreate, ReceiveRequest
from app.schemas.reorder import ReorderDraftPoCreate
from app.schemas.repeating_invoice import RepeatingInvoiceCreate
from app.schemas.role import RoleCreate
from app.schemas.settings import SettingsUpdate
from app.schemas.sku import SkuCreate
from app.schemas.stock_adjustment import StockAdjustmentCreate
from app.schemas.stock_return import StockReturnCreate
from app.schemas.stocktake import StocktakeCreate
from app.schemas.supplier import SupplierCreate
from app.schemas.transfer import TransferCreate
from app.schemas.user import ProfileUpdate, UserCreate, UserResponse
from app.schemas.vat201_period import Vat201PeriodCreate
from app.services.accounts import AccountService
from app.services.bank_imports import BankImportService
from app.services.bank_rules import BankRuleService
from app.services.bills import BillService
from app.services.category_maps import CategoryMapService
from app.services.contacts import ContactService
from app.services.cost_audit import CostAuditService
from app.services.credit_notes import CreditNoteService
from app.services.customers_crm import CustomersCrmService
from app.services.deliveries import DeliveriesService
from app.services.home import HomeService
from app.services.invoices import InvoiceService
from app.services.journals import JournalService
from app.services.laybys import LaybysService
from app.services.location_bins import LocationBinService
from app.services.locations import LocationService
from app.services.payments import PaymentService
from app.services.picks import PickService
from app.services.proformas import ProformaService
from app.services.purchase_orders import PurchaseOrderService
from app.services.reorder import ReorderService
from app.services.repeating_invoices import RepeatingInvoiceService
from app.services.reports import ReportsService
from app.services.roles import RoleService
from app.services.settings import SettingsService
from app.services.sku_bom import SkuBomService
from app.services.skus import SkuService
from app.services.stock_adjustments import StockAdjustmentService
from app.services.stock_returns import StockReturnsService
from app.services.stocktakes import StocktakeService
from app.services.suppliers import SupplierService
from app.services.transfers import TransferService
from app.services.users import ProfileService, UserService
from app.services.vat201_periods import Vat201PeriodService

_FILE_UPLOAD_HINT = "This action needs a file upload in the app — Nia cannot attach PDFs or photos."

_CAT = (CATALOGUE_MUTATE,)
_RECV = (STOCK_RECEIVE,)
_XFER = (STOCK_TRANSFER,)
_XFER_RECV = (STOCK_TRANSFER, TILL_SELL)
_PICKS = (STOCK_TRANSFER, TILL_SELL, SALES_DELIVERIES)
_CUST = (SALES_CUSTOMERS,)
_CUST_PATCH = (SALES_CUSTOMERS, USERS_MANAGE, PO_RAISE)
_RET = (SALES_RETURNS,)
_LAYBY = (SALES_LAYBYS,)
_DLV = (SALES_DELIVERIES,)
_BOOKS = (BOOKS_MUTATE,)
_OWNER = (USERS_MANAGE,)
_SETTINGS = (SETTINGS_MUTATE,)


def _as_of(data: ReportAsOfArgs) -> datetime.date:
    if data.as_of is not None:
        return data.as_of
    return datetime.date.today()


def _range(data: ReportRangeArgs) -> tuple[datetime.date, datetime.date]:
    today = datetime.date.today()
    start = data.from_date if data.from_date is not None else today.replace(day=1)
    end = data.to_date if data.to_date is not None else today
    return start, end


def _locations(rows: Any) -> list[LocationResponse]:
    return [LocationResponse.model_validate(row) for row in rows]


def _users(rows: Any) -> list[UserResponse]:
    return [UserResponse.model_validate(row) for row in rows]


async def _list_skus(deps: NiaDeps, data: ListSkusArgs) -> Any:
    return await SkuService(deps.db).list(data.category, deps.user_id)


async def _get_sku(deps: NiaDeps, data: SkuIdArgs) -> Any:
    return await SkuService(deps.db).get(data.sku_id, deps.user_id)


async def _create_sku(deps: NiaDeps, data: SkuCreate) -> Any:
    return await SkuService(deps.db).create(data, deps.user_id)


async def _update_sku(deps: NiaDeps, data: SkuUpdateArgs) -> Any:
    return await SkuService(deps.db).update(data.sku_id, data, deps.user_id)


async def _delete_sku(deps: NiaDeps, data: SkuIdArgs) -> Any:
    await SkuService(deps.db).delete(data.sku_id)
    return {"ok": True, "deleted_sku_id": str(data.sku_id)}


async def _get_sku_bom(deps: NiaDeps, data: SkuIdArgs) -> Any:
    return await SkuBomService(deps.db).list(data.sku_id)


async def _replace_sku_bom(deps: NiaDeps, data: SkuBomReplaceArgs) -> Any:
    return await SkuBomService(deps.db).replace(data.sku_id, data)


async def _list_suppliers(deps: NiaDeps, data: NiaEmptyArgs) -> Any:
    return await SupplierService(deps.db).list()


async def _create_supplier(deps: NiaDeps, data: SupplierCreate) -> Any:
    return await SupplierService(deps.db).create(data)


async def _list_proformas(deps: NiaDeps, data: NiaEmptyArgs) -> Any:
    return await ProformaService(deps.db).list()


async def _get_proforma(deps: NiaDeps, data: ProformaIdArgs) -> Any:
    return await ProformaService(deps.db).get(data.proforma_id)


async def _create_proforma(_deps: NiaDeps, _data: ProformaCreateArgs) -> Any:
    return _FILE_UPLOAD_HINT


async def _list_purchase_orders(deps: NiaDeps, data: NiaEmptyArgs) -> Any:
    return await PurchaseOrderService(deps.db).list()


async def _get_purchase_order(deps: NiaDeps, data: PurchaseOrderIdArgs) -> Any:
    return await PurchaseOrderService(deps.db).get(data.po_id)


async def _create_purchase_order(deps: NiaDeps, data: PurchaseOrderCreate) -> Any:
    return await PurchaseOrderService(deps.db).create(data)


async def _mark_on_water(deps: NiaDeps, data: PurchaseOrderIdArgs) -> Any:
    return await PurchaseOrderService(deps.db).mark_on_water(data.po_id)


async def _land_purchase_order(_deps: NiaDeps, _data: LandPurchaseOrderArgs) -> Any:
    return _FILE_UPLOAD_HINT


async def _receive_purchase_order(deps: NiaDeps, data: ReceiveRequest) -> Any:
    return await PurchaseOrderService(deps.db).receive(data, deps.user_id)


async def _list_reorder(deps: NiaDeps, data: NiaEmptyArgs) -> Any:
    return await ReorderService(deps.db).list()


async def _create_reorder_draft_po(deps: NiaDeps, data: ReorderDraftPoCreate) -> Any:
    return await ReorderService(deps.db).create_draft_pos(data)


async def _list_transfers(deps: NiaDeps, data: NiaEmptyArgs) -> Any:
    return await TransferService(deps.db).list()


async def _get_transfer(deps: NiaDeps, data: TransferIdArgs) -> Any:
    return await TransferService(deps.db).get(data.transfer_id)


async def _create_transfer(deps: NiaDeps, data: TransferCreate) -> Any:
    return await TransferService(deps.db).create(data, deps.user_id)


async def _dispatch_transfer(deps: NiaDeps, data: TransferIdArgs) -> Any:
    return await TransferService(deps.db).dispatch(data.transfer_id, deps.user_id)


async def _receive_transfer(deps: NiaDeps, data: ReceiveTransferArgs) -> Any:
    return await TransferService(deps.db).receive(data.transfer_id, data, deps.user_id)


async def _cancel_transfer(deps: NiaDeps, data: TransferIdArgs) -> Any:
    return await TransferService(deps.db).cancel(data.transfer_id, deps.user_id)


async def _list_adjustments(deps: NiaDeps, data: NiaEmptyArgs) -> Any:
    return await StockAdjustmentService(deps.db).list()


async def _get_adjustment(deps: NiaDeps, data: AdjustmentIdArgs) -> Any:
    return await StockAdjustmentService(deps.db).get(data.adjustment_id)


async def _create_adjustment(deps: NiaDeps, data: StockAdjustmentCreate) -> Any:
    return await StockAdjustmentService(deps.db).create(data, deps.user_id)


async def _add_adjustment_line(deps: NiaDeps, data: AddAdjustmentLineArgs) -> Any:
    return await StockAdjustmentService(deps.db).add_line(data.adjustment_id, data)


async def _update_adjustment_line(deps: NiaDeps, data: UpdateAdjustmentLineArgs) -> Any:
    return await StockAdjustmentService(deps.db).update_line(data.adjustment_id, data.line_id, data)


async def _delete_adjustment_line(deps: NiaDeps, data: DeleteAdjustmentLineArgs) -> Any:
    await StockAdjustmentService(deps.db).delete_line(data.adjustment_id, data.line_id)
    return {"ok": True}


async def _complete_adjustment(deps: NiaDeps, data: AdjustmentIdArgs) -> Any:
    return await StockAdjustmentService(deps.db).complete(data.adjustment_id, deps.user_id)


async def _cancel_adjustment(deps: NiaDeps, data: AdjustmentIdArgs) -> Any:
    return await StockAdjustmentService(deps.db).cancel(data.adjustment_id)


async def _list_stocktakes(deps: NiaDeps, data: NiaEmptyArgs) -> Any:
    return await StocktakeService(deps.db).list()


async def _get_stocktake(deps: NiaDeps, data: StocktakeIdArgs) -> Any:
    return await StocktakeService(deps.db).get(data.stocktake_id)


async def _lookup_stocktake(deps: NiaDeps, data: LookupStocktakeArgs) -> Any:
    return await StocktakeService(deps.db).lookup(data.stocktake_id, data)


async def _start_stocktake(deps: NiaDeps, data: StocktakeCreate) -> Any:
    return await StocktakeService(deps.db).start(data, deps.user_id)


async def _update_stocktake_line(deps: NiaDeps, data: UpdateStocktakeLineArgs) -> Any:
    return await StocktakeService(deps.db).update_line(data.stocktake_id, data.line_id, data)


async def _complete_stocktake(deps: NiaDeps, data: StocktakeIdArgs) -> Any:
    return await StocktakeService(deps.db).complete(data.stocktake_id, deps.user_id)


async def _cancel_stocktake(deps: NiaDeps, data: StocktakeIdArgs) -> Any:
    return await StocktakeService(deps.db).cancel(data.stocktake_id)


async def _correct_unit_cost(deps: NiaDeps, data: CorrectUnitCostArgs) -> Any:
    return await CostAuditService(deps.db).correct_unit_cost(data.sku_id, deps.user_id, data)


async def _list_locations(deps: NiaDeps, data: NiaEmptyArgs) -> Any:
    return _locations(await LocationService(deps.db).list())


async def _create_location(deps: NiaDeps, data: LocationCreate) -> Any:
    return LocationResponse.model_validate(await LocationService(deps.db).create(data))


async def _update_location(deps: NiaDeps, data: LocationUpdateArgs) -> Any:
    return LocationResponse.model_validate(
        await LocationService(deps.db).update(data.location_id, data)
    )


async def _list_bins(deps: NiaDeps, data: LocationIdArgs) -> Any:
    return await LocationBinService(deps.db).list(data.location_id)


async def _create_bin(deps: NiaDeps, data: CreateBinArgs) -> Any:
    return await LocationBinService(deps.db).create(data.location_id, data)


async def _generate_bin_grid(deps: NiaDeps, data: GenerateBinGridArgs) -> Any:
    return await LocationBinService(deps.db).generate_grid(data.location_id, data)


async def _update_bin(deps: NiaDeps, data: UpdateBinArgs) -> Any:
    return await LocationBinService(deps.db).update(data.location_id, data.bin_id, data)


async def _list_picks(deps: NiaDeps, data: NiaEmptyArgs) -> Any:
    return await PickService(deps.db).list()


async def _get_pick(deps: NiaDeps, data: PickIdArgs) -> Any:
    return await PickService(deps.db).get(data.pick_id)


async def _preview_pick(deps: NiaDeps, data: PickPreviewRequest) -> Any:
    return await PickService(deps.db).preview(data, deps.user_id)


async def _create_pick(deps: NiaDeps, data: PickCreate) -> Any:
    return await PickService(deps.db).create(data, deps.user_id)


async def _update_pick(deps: NiaDeps, data: UpdatePickArgs) -> Any:
    return await PickService(deps.db).update(data.pick_id, data)


async def _confirm_pick(deps: NiaDeps, data: ConfirmPickArgs) -> Any:
    return await PickService(deps.db).confirm(data.pick_id, data, deps.user_id)


async def _complete_pick(deps: NiaDeps, data: CompletePickArgs) -> Any:
    return await PickService(deps.db).complete(data.pick_id, data, deps.user_id)


async def _cancel_pick(deps: NiaDeps, data: PickIdArgs) -> Any:
    return await PickService(deps.db).cancel(data.pick_id)


async def _list_customers(deps: NiaDeps, data: NiaEmptyArgs) -> Any:
    return await CustomersCrmService(deps.db).list()


async def _get_customer(deps: NiaDeps, data: CustomerIdArgs) -> Any:
    return await CustomersCrmService(deps.db).get(data.customer_id)


async def _create_customer(deps: NiaDeps, data: CustomerCrmCreate) -> Any:
    return await CustomersCrmService(deps.db).create(data)


async def _update_customer(deps: NiaDeps, data: CustomerUpdateArgs) -> Any:
    return await CustomersCrmService(deps.db).update(data.customer_id, data, deps.user_id)


async def _list_returns(deps: NiaDeps, data: NiaEmptyArgs) -> Any:
    return await StockReturnsService(deps.db).list()


async def _get_return(deps: NiaDeps, data: ReturnIdArgs) -> Any:
    return await StockReturnsService(deps.db).get(data.return_id)


async def _create_return(deps: NiaDeps, data: StockReturnCreate) -> Any:
    return await StockReturnsService(deps.db).create(data, deps.user_id)


async def _complete_return(deps: NiaDeps, data: ReturnIdArgs) -> Any:
    return await StockReturnsService(deps.db).complete(data.return_id, deps.user_id)


async def _cancel_return(deps: NiaDeps, data: ReturnIdArgs) -> Any:
    return await StockReturnsService(deps.db).cancel(data.return_id)


async def _list_laybys(deps: NiaDeps, data: NiaEmptyArgs) -> Any:
    return await LaybysService(deps.db).list()


async def _get_layby(deps: NiaDeps, data: LaybyIdArgs) -> Any:
    return await LaybysService(deps.db).get(data.layby_id)


async def _create_layby(deps: NiaDeps, data: LaybyCreate) -> Any:
    return await LaybysService(deps.db).create(data, deps.user_id)


async def _add_layby_payment(deps: NiaDeps, data: AddLaybyPaymentArgs) -> Any:
    return await LaybysService(deps.db).add_payment(data.layby_id, data, deps.user_id)


async def _complete_layby(deps: NiaDeps, data: LaybyIdArgs) -> Any:
    return await LaybysService(deps.db).complete(data.layby_id, deps.user_id)


async def _cancel_layby(deps: NiaDeps, data: LaybyIdArgs) -> Any:
    return await LaybysService(deps.db).cancel(data.layby_id, deps.user_id)


async def _list_deliveries(deps: NiaDeps, data: NiaEmptyArgs) -> Any:
    return await DeliveriesService(deps.db).list()


async def _get_delivery(deps: NiaDeps, data: DeliveryIdArgs) -> Any:
    return await DeliveriesService(deps.db).get(data.delivery_id)


async def _create_delivery(deps: NiaDeps, data: DeliveryCreate) -> Any:
    return await DeliveriesService(deps.db).create(data, deps.user_id)


async def _pack_delivery(deps: NiaDeps, data: DeliveryIdArgs) -> Any:
    return await DeliveriesService(deps.db).pack(data.delivery_id)


async def _complete_delivery(deps: NiaDeps, data: CompleteDeliveryArgs) -> Any:
    return await DeliveriesService(deps.db).complete(data.delivery_id, data)


async def _cancel_delivery(deps: NiaDeps, data: DeliveryIdArgs) -> Any:
    return await DeliveriesService(deps.db).cancel(data.delivery_id)


async def _list_accounts(deps: NiaDeps, data: NiaEmptyArgs) -> Any:
    return await AccountService(deps.db).list()


async def _create_account(deps: NiaDeps, data: AccountCreate) -> Any:
    return await AccountService(deps.db).create(data)


async def _update_account(deps: NiaDeps, data: AccountUpdateArgs) -> Any:
    return await AccountService(deps.db).update(data.account_id, data)


async def _list_contacts(deps: NiaDeps, data: NiaEmptyArgs) -> Any:
    return await ContactService(deps.db).list()


async def _create_contact(deps: NiaDeps, data: ContactCreate) -> Any:
    return await ContactService(deps.db).create_customer(data)


async def _list_invoices(deps: NiaDeps, data: NiaEmptyArgs) -> Any:
    return await InvoiceService(deps.db).list()


async def _get_invoice(deps: NiaDeps, data: InvoiceIdArgs) -> Any:
    return await InvoiceService(deps.db).get(data.invoice_id)


async def _create_invoice(deps: NiaDeps, data: InvoiceCreate) -> Any:
    return await InvoiceService(deps.db).create(data, deps.user_id)


async def _list_bills(deps: NiaDeps, data: NiaEmptyArgs) -> Any:
    return await BillService(deps.db).list()


async def _get_bill(deps: NiaDeps, data: BillIdArgs) -> Any:
    return await BillService(deps.db).get(data.bill_id)


async def _create_bill(deps: NiaDeps, data: BillCreate) -> Any:
    return await BillService(deps.db).create(data, deps.user_id)


async def _list_credit_notes(deps: NiaDeps, data: NiaEmptyArgs) -> Any:
    return await CreditNoteService(deps.db).list()


async def _get_credit_note(deps: NiaDeps, data: CreditNoteIdArgs) -> Any:
    return await CreditNoteService(deps.db).get(data.credit_note_id)


async def _create_credit_note(deps: NiaDeps, data: CreditNoteCreate) -> Any:
    return await CreditNoteService(deps.db).create(data)


async def _list_payments(deps: NiaDeps, data: NiaEmptyArgs) -> Any:
    return await PaymentService(deps.db).list()


async def _create_payment(deps: NiaDeps, data: PaymentCreate) -> Any:
    return await PaymentService(deps.db).create(data, deps.user_id)


async def _list_journals(deps: NiaDeps, data: NiaEmptyArgs) -> Any:
    return await JournalService(deps.db).list()


async def _get_journal(deps: NiaDeps, data: JournalIdArgs) -> Any:
    return await JournalService(deps.db).get(data.journal_id)


async def _create_journal(deps: NiaDeps, data: JournalCreate) -> Any:
    return await JournalService(deps.db).create(data, deps.user_id)


async def _post_journal(deps: NiaDeps, data: JournalIdArgs) -> Any:
    return await JournalService(deps.db).post(data.journal_id, deps.user_id)


async def _void_journal(deps: NiaDeps, data: JournalIdArgs) -> Any:
    return await JournalService(deps.db).void(data.journal_id, deps.user_id)


async def _list_repeating_invoices(deps: NiaDeps, data: NiaEmptyArgs) -> Any:
    return await RepeatingInvoiceService(deps.db).list()


async def _get_repeating_invoice(deps: NiaDeps, data: RepeatingInvoiceIdArgs) -> Any:
    return await RepeatingInvoiceService(deps.db).get(data.schedule_id)


async def _create_repeating_invoice(deps: NiaDeps, data: RepeatingInvoiceCreate) -> Any:
    return await RepeatingInvoiceService(deps.db).create(data, deps.user_id)


async def _update_repeating_invoice(deps: NiaDeps, data: RepeatingInvoiceUpdateArgs) -> Any:
    return await RepeatingInvoiceService(deps.db).update(data.schedule_id, data)


async def _run_repeating_invoice(deps: NiaDeps, data: RepeatingInvoiceIdArgs) -> Any:
    return await RepeatingInvoiceService(deps.db).run(data.schedule_id, deps.user_id)


async def _create_bank_rule(deps: NiaDeps, data: BankRuleCreate) -> Any:
    return await BankRuleService(deps.db).create(data)


async def _update_bank_rule(deps: NiaDeps, data: BankRuleUpdateArgs) -> Any:
    return await BankRuleService(deps.db).update(data.rule_id, data)


async def _delete_bank_rule(deps: NiaDeps, data: BankRuleIdArgs) -> Any:
    await BankRuleService(deps.db).delete(data.rule_id)
    return {"ok": True}


async def _match_bank_line(deps: NiaDeps, data: MatchBankLineArgs) -> Any:
    return await BankImportService(deps.db).match_line(data.import_id, data.line_id, data)


async def _apply_bank_rule(deps: NiaDeps, data: ApplyBankRuleArgs) -> Any:
    return await BankImportService(deps.db).apply_rule(data.import_id, data.line_id, data)


async def _recode_bank_line(deps: NiaDeps, data: RecodeBankLineArgs) -> Any:
    return await BankImportService(deps.db).recode(data.import_id, data.line_id, data)


async def _upsert_category_map(deps: NiaDeps, data: CategoryAccountMapUpsert) -> Any:
    return await CategoryMapService(deps.db).upsert(data)


async def _list_vat201_periods(deps: NiaDeps, data: NiaEmptyArgs) -> Any:
    return await Vat201PeriodService(deps.db).list()


async def _get_vat201_period(deps: NiaDeps, data: PeriodIdArgs) -> Any:
    return await Vat201PeriodService(deps.db).get(data.period_id)


async def _create_period(deps: NiaDeps, data: Vat201PeriodCreate) -> Any:
    return await Vat201PeriodService(deps.db).create(data)


async def _lock_period(deps: NiaDeps, data: PeriodIdArgs) -> Any:
    return await Vat201PeriodService(deps.db).lock(data.period_id, deps.user_id)


async def _reopen_period(deps: NiaDeps, data: ReopenPeriodArgs) -> Any:
    return await Vat201PeriodService(deps.db).reopen(data.period_id, deps.user_id, data)


async def _list_users(deps: NiaDeps, data: NiaEmptyArgs) -> Any:
    return _users(await UserService(deps.db).list())


async def _create_user(deps: NiaDeps, data: UserCreate) -> Any:
    return UserResponse.model_validate(await UserService(deps.db).create(data))


async def _update_user(deps: NiaDeps, data: UserUpdateArgs) -> Any:
    return UserResponse.model_validate(await UserService(deps.db).update(data.user_id, data))


async def _update_profile(deps: NiaDeps, data: ProfileUpdate) -> Any:
    return UserResponse.model_validate(await ProfileService(deps.db).update(deps.user_id, data))


async def _list_roles(deps: NiaDeps, data: NiaEmptyArgs) -> Any:
    return await RoleService(deps.db).list()


async def _create_role(deps: NiaDeps, data: RoleCreate) -> Any:
    return await RoleService(deps.db).create(data)


async def _update_role(deps: NiaDeps, data: RoleUpdateArgs) -> Any:
    return await RoleService(deps.db).update(data.role_id, data)


async def _delete_role(deps: NiaDeps, data: RoleIdArgs) -> Any:
    await RoleService(deps.db).delete(data.role_id)
    return {"ok": True}


async def _get_settings(deps: NiaDeps, data: NiaEmptyArgs) -> Any:
    return await SettingsService(deps.db).get_for_user(deps.user_id)


async def _update_settings(deps: NiaDeps, data: SettingsUpdate) -> Any:
    return await SettingsService(deps.db).update(deps.user_id, data)


async def _home_summary(deps: NiaDeps, data: NiaEmptyArgs) -> Any:
    return await HomeService(deps.db).summary()


async def _aged_ar(deps: NiaDeps, data: ReportAsOfArgs) -> Any:
    return await ReportsService(deps.db).aged_ar(_as_of(data))


async def _aged_ap(deps: NiaDeps, data: ReportAsOfArgs) -> Any:
    return await ReportsService(deps.db).aged_ap(_as_of(data))


async def _profit_loss(deps: NiaDeps, data: ReportRangeArgs) -> Any:
    start, end = _range(data)
    return await ReportsService(deps.db).profit_loss(start, end)


async def _balance_sheet(deps: NiaDeps, data: ReportAsOfArgs) -> Any:
    return await ReportsService(deps.db).balance_sheet(_as_of(data))


async def _stock_valuation(deps: NiaDeps, data: NiaEmptyArgs) -> Any:
    return await ReportsService(deps.db).stock_valuation()


async def _sales_by_sku(deps: NiaDeps, data: ReportRangeArgs) -> Any:
    start, end = _range(data)
    return await ReportsService(deps.db).sales_by_sku(start, end)


async def _trial_balance(deps: NiaDeps, data: ReportAsOfArgs) -> Any:
    return await ReportsService(deps.db).trial_balance(_as_of(data))


async def _vat201_draft(deps: NiaDeps, data: ReportRangeArgs) -> Any:
    start, end = _range(data)
    return await ReportsService(deps.db).vat201_draft(start, end)


def _a(
    action_id: str,
    title: str,
    permission: Any,
    write: bool,
    args_model: Any,
    handler: Any,
) -> NiaAction:
    return NiaAction(
        id=action_id,
        title=title,
        permission=permission,
        write=write,
        args_model=args_model,
        handler=handler,
    )


CATALOG: tuple[NiaAction, ...] = (
    _a("list_skus", "List SKUs", None, False, ListSkusArgs, _list_skus),
    _a("get_sku", "Get SKU", None, False, SkuIdArgs, _get_sku),
    _a("create_sku", "Create SKU", _CAT, True, SkuCreate, _create_sku),
    _a("update_sku", "Update SKU", _CAT, True, SkuUpdateArgs, _update_sku),
    _a("delete_sku", "Delete SKU", _CAT, True, SkuIdArgs, _delete_sku),
    _a("get_sku_bom", "Get SKU BOM", None, False, SkuIdArgs, _get_sku_bom),
    _a("replace_sku_bom", "Replace SKU BOM", _CAT, True, SkuBomReplaceArgs, _replace_sku_bom),
    _a("list_suppliers", "List suppliers", None, False, NiaEmptyArgs, _list_suppliers),
    _a("create_supplier", "Create supplier", _CAT, True, SupplierCreate, _create_supplier),
    _a("list_proformas", "List proformas", None, False, NiaEmptyArgs, _list_proformas),
    _a("get_proforma", "Get proforma", None, False, ProformaIdArgs, _get_proforma),
    _a("create_proforma", "Create proforma", _CAT, True, ProformaCreateArgs, _create_proforma),
    _a(
        "list_purchase_orders",
        "List purchase orders",
        None,
        False,
        NiaEmptyArgs,
        _list_purchase_orders,
    ),
    _a(
        "get_purchase_order",
        "Get purchase order",
        None,
        False,
        PurchaseOrderIdArgs,
        _get_purchase_order,
    ),
    _a(
        "create_purchase_order",
        "Create purchase order",
        _CAT,
        True,
        PurchaseOrderCreate,
        _create_purchase_order,
    ),
    _a("mark_on_water", "Mark PO on water", _CAT, True, PurchaseOrderIdArgs, _mark_on_water),
    _a(
        "land_purchase_order",
        "Land purchase order",
        _CAT,
        True,
        LandPurchaseOrderArgs,
        _land_purchase_order,
    ),
    _a("list_reorder", "List reorder", None, False, NiaEmptyArgs, _list_reorder),
    _a(
        "create_reorder_draft_po",
        "Create reorder draft POs",
        _CAT,
        True,
        ReorderDraftPoCreate,
        _create_reorder_draft_po,
    ),
    _a(
        "receive_purchase_order",
        "Receive purchase order",
        _RECV,
        True,
        ReceiveRequest,
        _receive_purchase_order,
    ),
    _a("list_transfers", "List transfers", None, False, NiaEmptyArgs, _list_transfers),
    _a("get_transfer", "Get transfer", None, False, TransferIdArgs, _get_transfer),
    _a("create_transfer", "Create transfer", _XFER, True, TransferCreate, _create_transfer),
    _a("dispatch_transfer", "Dispatch transfer", _XFER, True, TransferIdArgs, _dispatch_transfer),
    _a(
        "receive_transfer",
        "Receive transfer",
        _XFER_RECV,
        True,
        ReceiveTransferArgs,
        _receive_transfer,
    ),
    _a("cancel_transfer", "Cancel transfer", _XFER, True, TransferIdArgs, _cancel_transfer),
    _a("list_adjustments", "List adjustments", None, False, NiaEmptyArgs, _list_adjustments),
    _a("get_adjustment", "Get adjustment", None, False, AdjustmentIdArgs, _get_adjustment),
    _a(
        "create_adjustment",
        "Create adjustment",
        _RECV,
        True,
        StockAdjustmentCreate,
        _create_adjustment,
    ),
    _a(
        "add_adjustment_line",
        "Add adjustment line",
        _RECV,
        True,
        AddAdjustmentLineArgs,
        _add_adjustment_line,
    ),
    _a(
        "update_adjustment_line",
        "Update adjustment line",
        _RECV,
        True,
        UpdateAdjustmentLineArgs,
        _update_adjustment_line,
    ),
    _a(
        "delete_adjustment_line",
        "Delete adjustment line",
        _RECV,
        True,
        DeleteAdjustmentLineArgs,
        _delete_adjustment_line,
    ),
    _a(
        "complete_adjustment",
        "Complete adjustment",
        _RECV,
        True,
        AdjustmentIdArgs,
        _complete_adjustment,
    ),
    _a("cancel_adjustment", "Cancel adjustment", _RECV, True, AdjustmentIdArgs, _cancel_adjustment),
    _a("list_stocktakes", "List stocktakes", None, False, NiaEmptyArgs, _list_stocktakes),
    _a("get_stocktake", "Get stocktake", None, False, StocktakeIdArgs, _get_stocktake),
    _a(
        "lookup_stocktake",
        "Lookup stocktake barcode",
        _RECV,
        False,
        LookupStocktakeArgs,
        _lookup_stocktake,
    ),
    _a("start_stocktake", "Start stocktake", _RECV, True, StocktakeCreate, _start_stocktake),
    _a(
        "update_stocktake_line",
        "Update stocktake line",
        _RECV,
        True,
        UpdateStocktakeLineArgs,
        _update_stocktake_line,
    ),
    _a(
        "complete_stocktake",
        "Complete stocktake",
        _RECV,
        True,
        StocktakeIdArgs,
        _complete_stocktake,
    ),
    _a("cancel_stocktake", "Cancel stocktake", _RECV, True, StocktakeIdArgs, _cancel_stocktake),
    _a(
        "correct_unit_cost",
        "Correct unit cost",
        _OWNER,
        True,
        CorrectUnitCostArgs,
        _correct_unit_cost,
    ),
    _a("list_locations", "List locations", None, False, NiaEmptyArgs, _list_locations),
    _a("create_location", "Create location", _RECV, True, LocationCreate, _create_location),
    _a("update_location", "Update location", _RECV, True, LocationUpdateArgs, _update_location),
    _a("list_bins", "List bins", None, False, LocationIdArgs, _list_bins),
    _a("create_bin", "Create bin", _RECV, True, CreateBinArgs, _create_bin),
    _a(
        "generate_bin_grid",
        "Generate bin grid",
        _RECV,
        True,
        GenerateBinGridArgs,
        _generate_bin_grid,
    ),
    _a("update_bin", "Update bin", _RECV, True, UpdateBinArgs, _update_bin),
    _a("list_picks", "List picks", None, False, NiaEmptyArgs, _list_picks),
    _a("get_pick", "Get pick", None, False, PickIdArgs, _get_pick),
    _a("preview_pick", "Preview pick", _PICKS, False, PickPreviewRequest, _preview_pick),
    _a("create_pick", "Create pick", _PICKS, True, PickCreate, _create_pick),
    _a("update_pick", "Update pick", _PICKS, True, UpdatePickArgs, _update_pick),
    _a("confirm_pick", "Confirm pick", _PICKS, True, ConfirmPickArgs, _confirm_pick),
    _a("complete_pick", "Complete pick", _PICKS, True, CompletePickArgs, _complete_pick),
    _a("cancel_pick", "Cancel pick", _PICKS, True, PickIdArgs, _cancel_pick),
    _a("list_customers", "List customers", None, False, NiaEmptyArgs, _list_customers),
    _a("get_customer", "Get customer", None, False, CustomerIdArgs, _get_customer),
    _a("create_customer", "Create customer", _CUST, True, CustomerCrmCreate, _create_customer),
    _a(
        "update_customer",
        "Update customer",
        _CUST_PATCH,
        True,
        CustomerUpdateArgs,
        _update_customer,
    ),
    _a("list_returns", "List returns", None, False, NiaEmptyArgs, _list_returns),
    _a("get_return", "Get return", None, False, ReturnIdArgs, _get_return),
    _a("create_return", "Create return", _RET, True, StockReturnCreate, _create_return),
    _a("complete_return", "Complete return", _RET, True, ReturnIdArgs, _complete_return),
    _a("cancel_return", "Cancel return", _RET, True, ReturnIdArgs, _cancel_return),
    _a("list_laybys", "List laybys", None, False, NiaEmptyArgs, _list_laybys),
    _a("get_layby", "Get layby", None, False, LaybyIdArgs, _get_layby),
    _a("create_layby", "Create layby", _LAYBY, True, LaybyCreate, _create_layby),
    _a(
        "add_layby_payment",
        "Add layby payment",
        _LAYBY,
        True,
        AddLaybyPaymentArgs,
        _add_layby_payment,
    ),
    _a("complete_layby", "Complete layby", _LAYBY, True, LaybyIdArgs, _complete_layby),
    _a("cancel_layby", "Cancel layby", _LAYBY, True, LaybyIdArgs, _cancel_layby),
    _a("list_deliveries", "List deliveries", None, False, NiaEmptyArgs, _list_deliveries),
    _a("get_delivery", "Get delivery", None, False, DeliveryIdArgs, _get_delivery),
    _a("create_delivery", "Create delivery", _DLV, True, DeliveryCreate, _create_delivery),
    _a("pack_delivery", "Pack delivery", _DLV, True, DeliveryIdArgs, _pack_delivery),
    _a(
        "complete_delivery",
        "Complete delivery",
        _DLV,
        True,
        CompleteDeliveryArgs,
        _complete_delivery,
    ),
    _a("cancel_delivery", "Cancel delivery", _DLV, True, DeliveryIdArgs, _cancel_delivery),
    _a("list_accounts", "List accounts", None, False, NiaEmptyArgs, _list_accounts),
    _a("create_account", "Create account", _BOOKS, True, AccountCreate, _create_account),
    _a("update_account", "Update account", _BOOKS, True, AccountUpdateArgs, _update_account),
    _a("list_contacts", "List contacts", None, False, NiaEmptyArgs, _list_contacts),
    _a("create_contact", "Create contact", _BOOKS, True, ContactCreate, _create_contact),
    _a("list_invoices", "List invoices", None, False, NiaEmptyArgs, _list_invoices),
    _a("get_invoice", "Get invoice", None, False, InvoiceIdArgs, _get_invoice),
    _a("create_invoice", "Create invoice", _BOOKS, True, InvoiceCreate, _create_invoice),
    _a("list_bills", "List bills", None, False, NiaEmptyArgs, _list_bills),
    _a("get_bill", "Get bill", None, False, BillIdArgs, _get_bill),
    _a("create_bill", "Create bill", _BOOKS, True, BillCreate, _create_bill),
    _a("list_credit_notes", "List credit notes", None, False, NiaEmptyArgs, _list_credit_notes),
    _a("get_credit_note", "Get credit note", None, False, CreditNoteIdArgs, _get_credit_note),
    _a(
        "create_credit_note",
        "Create credit note",
        _BOOKS,
        True,
        CreditNoteCreate,
        _create_credit_note,
    ),
    _a("list_payments", "List payments", None, False, NiaEmptyArgs, _list_payments),
    _a("create_payment", "Create payment", _BOOKS, True, PaymentCreate, _create_payment),
    _a("list_journals", "List journals", None, False, NiaEmptyArgs, _list_journals),
    _a("get_journal", "Get journal", None, False, JournalIdArgs, _get_journal),
    _a("create_journal", "Create journal", _BOOKS, True, JournalCreate, _create_journal),
    _a("post_journal", "Post journal", _BOOKS, True, JournalIdArgs, _post_journal),
    _a("void_journal", "Void journal", _BOOKS, True, JournalIdArgs, _void_journal),
    _a(
        "list_repeating_invoices",
        "List repeating invoices",
        None,
        False,
        NiaEmptyArgs,
        _list_repeating_invoices,
    ),
    _a(
        "get_repeating_invoice",
        "Get repeating invoice",
        None,
        False,
        RepeatingInvoiceIdArgs,
        _get_repeating_invoice,
    ),
    _a(
        "create_repeating_invoice",
        "Create repeating invoice",
        _BOOKS,
        True,
        RepeatingInvoiceCreate,
        _create_repeating_invoice,
    ),
    _a(
        "update_repeating_invoice",
        "Update repeating invoice",
        _BOOKS,
        True,
        RepeatingInvoiceUpdateArgs,
        _update_repeating_invoice,
    ),
    _a(
        "run_repeating_invoice",
        "Run repeating invoice",
        _BOOKS,
        True,
        RepeatingInvoiceIdArgs,
        _run_repeating_invoice,
    ),
    _a("create_bank_rule", "Create bank rule", _BOOKS, True, BankRuleCreate, _create_bank_rule),
    _a("update_bank_rule", "Update bank rule", _BOOKS, True, BankRuleUpdateArgs, _update_bank_rule),
    _a("delete_bank_rule", "Delete bank rule", _BOOKS, True, BankRuleIdArgs, _delete_bank_rule),
    _a("match_bank_line", "Match bank line", _BOOKS, True, MatchBankLineArgs, _match_bank_line),
    _a("apply_bank_rule", "Apply bank rule", _BOOKS, True, ApplyBankRuleArgs, _apply_bank_rule),
    _a("recode_bank_line", "Recode bank line", _BOOKS, True, RecodeBankLineArgs, _recode_bank_line),
    _a(
        "upsert_category_map",
        "Upsert category map",
        _BOOKS,
        True,
        CategoryAccountMapUpsert,
        _upsert_category_map,
    ),
    _a(
        "list_vat201_periods",
        "List VAT201 periods",
        None,
        False,
        NiaEmptyArgs,
        _list_vat201_periods,
    ),
    _a("get_vat201_period", "Get VAT201 period", None, False, PeriodIdArgs, _get_vat201_period),
    _a("create_period", "Create VAT201 period", _BOOKS, True, Vat201PeriodCreate, _create_period),
    _a("lock_period", "Lock VAT201 period", _BOOKS, True, PeriodIdArgs, _lock_period),
    _a("reopen_period", "Reopen VAT201 period", _OWNER, True, ReopenPeriodArgs, _reopen_period),
    _a("list_users", "List users", _OWNER, False, NiaEmptyArgs, _list_users),
    _a("create_user", "Create user", _OWNER, True, UserCreate, _create_user),
    _a("update_user", "Update user", _OWNER, True, UserUpdateArgs, _update_user),
    _a("update_profile", "Update profile", None, True, ProfileUpdate, _update_profile),
    _a("list_roles", "List roles", _OWNER, False, NiaEmptyArgs, _list_roles),
    _a("create_role", "Create role", _OWNER, True, RoleCreate, _create_role),
    _a("update_role", "Update role", _OWNER, True, RoleUpdateArgs, _update_role),
    _a("delete_role", "Delete role", _OWNER, True, RoleIdArgs, _delete_role),
    _a("get_settings", "Get settings", None, False, NiaEmptyArgs, _get_settings),
    _a("update_settings", "Update settings", _SETTINGS, True, SettingsUpdate, _update_settings),
    _a("home_summary", "Home summary", None, False, NiaEmptyArgs, _home_summary),
    _a("aged_ar", "Aged receivables", None, False, ReportAsOfArgs, _aged_ar),
    _a("aged_ap", "Aged payables", None, False, ReportAsOfArgs, _aged_ap),
    _a("profit_loss", "Profit and loss", None, False, ReportRangeArgs, _profit_loss),
    _a("balance_sheet", "Balance sheet", None, False, ReportAsOfArgs, _balance_sheet),
    _a("stock_valuation", "Stock valuation", None, False, NiaEmptyArgs, _stock_valuation),
    _a("sales_by_sku", "Sales by SKU", None, False, ReportRangeArgs, _sales_by_sku),
    _a("trial_balance", "Trial balance", None, False, ReportAsOfArgs, _trial_balance),
    _a("vat201_draft", "VAT201 draft", None, False, ReportRangeArgs, _vat201_draft),
)

CATALOG_BY_ID: dict[str, NiaAction] = {action.id: action for action in CATALOG}
