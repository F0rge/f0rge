"""The allowlisted Firstout actions available through MCP's compact discovery tools."""

from __future__ import annotations

from uuid import UUID

from f0rge_core.exceptions import NotFoundError
from pydantic import Field
from pydantic_core import to_jsonable_python
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.sku import SkuCRUD
from app.models.account import Account
from app.models.bill import Bill
from app.models.credit_note import CreditNote
from app.models.customer import Customer
from app.models.delivery import Delivery
from app.models.inventory import LocationStock, SkuStock
from app.models.journal import JournalEntry
from app.models.layby import Layby
from app.models.location import Location
from app.models.location_bin import LocationBin
from app.models.mcp_token import McpToken
from app.models.payment import Payment
from app.models.pick import Pick
from app.models.price_list import PriceList
from app.models.proforma import Proforma
from app.models.purchase_order import PurchaseOrder
from app.models.quote import Quote
from app.models.repeating_invoice import RepeatingInvoice
from app.models.role import Role
from app.models.sales_order import SalesOrder
from app.models.stock_adjustment import StockAdjustment
from app.models.stock_return import StockReturn
from app.models.stocktake import Stocktake
from app.models.supplier import Supplier
from app.models.tax_invoice import TaxInvoice
from app.models.transfer import Transfer, TransferLine, TransferStatus
from app.permissions import TILL_SELL, USERS_MANAGE
from app.schemas.till import TillPriceRequest, TillSaleLineCreate
from app.services.mcp_action_types import (
    Action,
    Arguments,
    FindRecords,
    PageArguments,
    SearchText,
    paged_rows,
)
from app.services.mcp_tab_reads import TAB_READ_ACTIONS
from app.services.permissions import PermissionService
from app.services.records import RecordsService
from app.services.till_orchestrator import TillOrchestrator
from app.services.till_seed import WALK_IN_CUSTOMER_NAME


class FindProducts(FindRecords):
    query: SearchText


class StockBins(FindRecords):
    location_id: UUID | None = None
    sku_id: UUID | None = None


class LocationBins(PageArguments):
    location_id: UUID


class OnHand(PageArguments):
    sku_id: UUID
    location_id: UUID | None = None


class FindTransfers(FindRecords):
    status: TransferStatus | None = None


class GetTransfer(PageArguments):
    transfer_id: UUID


class PricePreview(Arguments):
    sku_id: UUID
    quantity: int = Field(default=1, ge=1, le=10000)
    customer_id: UUID | None = None


async def _products(db: AsyncSession, token: McpToken, args: FindProducts) -> dict:
    skus, total = await SkuCRUD(db).list_filtered(
        q=args.query, limit=args.limit, offset=args.offset
    )
    return {
        "items": [
            {"id": str(sku.id), "sku": sku.our_ref, "name": sku.name, "category": sku.category}
            for sku in skus
        ],
        "total": total,
    }


async def _home(db: AsyncSession, token: McpToken, args: Arguments) -> dict:
    # The Home tiles report physical quantity at locations with positive stock.
    on_hand = select(func.coalesce(func.sum(LocationStock.on_hand), 0)).where(
        LocationStock.team_id == token.team_id, LocationStock.on_hand > 0
    )
    on_order = select(func.coalesce(func.sum(SkuStock.on_order), 0)).where(
        SkuStock.team_id == token.team_id
    )
    result = await db.execute(
        select(
            on_hand.scalar_subquery().label("on_hand_qty"),
            on_order.scalar_subquery().label("on_order_qty"),
        )
    )
    return to_jsonable_python(dict(result.mappings().one()))


async def _bins(db: AsyncSession, token: McpToken, args: LocationBins) -> dict:
    stmt = (
        select(LocationBin.id, LocationBin.code, LocationBin.is_default)
        .where(
            LocationBin.team_id == token.team_id,
            LocationBin.location_id == args.location_id,
            LocationBin.is_archived.is_(False),
        )
        .order_by(LocationBin.is_default.desc(), LocationBin.code, LocationBin.id)
    )
    return await paged_rows(db, stmt, args)


async def _on_hand(db: AsyncSession, token: McpToken, args: OnHand) -> dict:
    stmt = (
        select(
            LocationStock.sku_id,
            LocationStock.location_id,
            Location.name.label("location_name"),
            LocationStock.on_hand,
        )
        .join(Location, Location.id == LocationStock.location_id)
        .where(
            LocationStock.team_id == token.team_id,
            Location.team_id == token.team_id,
            LocationStock.sku_id == args.sku_id,
        )
        .order_by(Location.name, Location.id)
    )
    if args.location_id is not None:
        stmt = stmt.where(LocationStock.location_id == args.location_id)
    return await paged_rows(db, stmt, args)


async def _bin_stock(db: AsyncSession, token: McpToken, args: StockBins) -> dict:
    result = await RecordsService(db).stock_by_bin(
        args.page(), args.location_id, sku_id=args.sku_id
    )
    return result.model_dump(mode="json")


def _transfer_summary():
    return select(
        Transfer.id,
        Transfer.transfer_number,
        Transfer.status,
        Transfer.from_location_id,
        Transfer.to_location_id,
        Transfer.dispatched_at,
        Transfer.received_at,
    )


async def _transfers(db: AsyncSession, token: McpToken, args: FindTransfers) -> dict:
    stmt = _transfer_summary().where(Transfer.team_id == token.team_id)
    if args.status is not None:
        stmt = stmt.where(Transfer.status == args.status)
    if args.query is not None:
        stmt = stmt.where(Transfer.transfer_number.icontains(args.query, autoescape=True))
    return await paged_rows(db, stmt.order_by(Transfer.created_at.desc(), Transfer.id), args)


async def _transfer(db: AsyncSession, token: McpToken, args: GetTransfer) -> dict:
    record = await db.execute(
        _transfer_summary().where(
            Transfer.id == args.transfer_id, Transfer.team_id == token.team_id
        )
    )
    header = record.mappings().one_or_none()
    if header is None:
        raise NotFoundError("Transfer not found")
    stmt = (
        select(
            TransferLine.id.label("line_id"),
            TransferLine.sku_id,
            TransferLine.qty_dispatched,
            TransferLine.qty_received,
            TransferLine.from_bin_id,
            TransferLine.to_bin_id,
        )
        .where(TransferLine.transfer_id == args.transfer_id, TransferLine.team_id == token.team_id)
        .order_by(TransferLine.id)
    )
    page = await paged_rows(db, stmt, args)
    return {
        **to_jsonable_python(dict(header)),
        "lines": page["items"],
        "next_offset": page["next_offset"],
    }


async def _price(db: AsyncSession, token: McpToken, args: PricePreview) -> dict:
    customer_filter = (
        Customer.id == args.customer_id
        if args.customer_id is not None
        else Customer.name == WALK_IN_CUSTOMER_NAME
    )
    customer_id = await db.scalar(
        select(Customer.id).where(Customer.team_id == token.team_id, customer_filter)
    )
    if customer_id is None:
        raise NotFoundError("Customer not found")
    body = TillPriceRequest(
        customer_id=customer_id, lines=[TillSaleLineCreate(sku_id=args.sku_id, qty=args.quantity)]
    )
    preview = await TillOrchestrator(db).preview_prices(body, token.user_id)
    return preview.model_dump(
        mode="json", include={"subtotal_ex_vat", "vat_amount", "total_inc_vat"}
    )


async def _my_access(db: AsyncSession, token: McpToken, args: Arguments) -> dict:
    return {"permissions": await PermissionService(db).keys_for_user(token.user_id)}


def _directory(
    name, tab, description, model, columns, search_columns, *, permissions=(), active_only=True
):
    # Columns and search keys come exclusively from this file. No caller-supplied
    # field, ORM class, order expression or permission is accepted.
    async def lookup(db: AsyncSession, token: McpToken, args: FindRecords) -> dict:
        stmt = select(model.id, *columns).where(model.team_id == token.team_id)
        if active_only:
            stmt = stmt.where(model.is_archived.is_(False))
        if args.query is not None:
            stmt = stmt.where(
                or_(*(column.icontains(args.query, autoescape=True) for column in search_columns))
            )
        return await paged_rows(db, stmt.order_by(*search_columns, model.id), args)

    return Action(name, tab, description, FindRecords, permissions, lookup)


def _documents(name, tab, description, model, reference, fields):
    # These lookups search the declared reference, name or status. Never search free-text
    # notes, addresses or contacts, even when only a document count is returned.
    return _directory(
        name, tab, description, model, (reference, *fields), (reference,), active_only=False
    )


READ_ACTIONS: tuple[Action, ...] = (
    *TAB_READ_ACTIONS,
    Action(
        "home_summary",
        "Home",
        "Summarise the quantities currently on hand and on order in your business.",
        Arguments,
        (),
        _home,
    ),
    Action(
        "catalogue_search",
        "Catalogue / Catalogue",
        "Find active products by name, SKU code or barcode.",
        FindProducts,
        (),
        _products,
    ),
    _directory(
        "locations_list",
        "Catalogue / Locations",
        "Find active warehouses and showrooms by name.",
        Location,
        (Location.name, Location.type),
        (Location.name,),
    ),
    Action(
        "location_bins_list",
        "Catalogue / Locations",
        "List active bins at a location, including the default bin.",
        LocationBins,
        (),
        _bins,
    ),
    _directory(
        "suppliers_find",
        "Catalogue / Suppliers",
        "Find active suppliers and their trading currency.",
        Supplier,
        (Supplier.name, Supplier.default_currency),
        (Supplier.name,),
    ),
    _directory(
        "price_lists_find",
        "Catalogue / Price lists",
        "Find active price lists by name.",
        PriceList,
        (PriceList.name,),
        (PriceList.name,),
    ),
    _directory(
        "proformas_find",
        "Catalogue / Proformas",
        "Find active supplier proformas by invoice number.",
        Proforma,
        (Proforma.invoice_number, Proforma.invoice_date, Proforma.currency),
        (Proforma.invoice_number,),
    ),
    _documents(
        "stocktakes_find",
        "Stock / Stocktakes",
        "Find physical stock counts by status and check their location.",
        Stocktake,
        Stocktake.status,
        (Stocktake.location_id, Stocktake.started_at, Stocktake.completed_at),
    ),
    _documents(
        "adjustments_find",
        "Stock / Adjustments",
        "Find stock adjustments by status and check their location.",
        StockAdjustment,
        StockAdjustment.status,
        (StockAdjustment.location_id,),
    ),
    Action(
        "stock_on_hand",
        "Stock / Stock by bin",
        "Look up on-hand quantity for a SKU across locations or at one location.",
        OnHand,
        (),
        _on_hand,
    ),
    Action(
        "stock_by_bin",
        "Stock / Stock by bin",
        "Locate stock by SKU, warehouse and bin with its on-hand quantity.",
        StockBins,
        (),
        _bin_stock,
        related_tabs=("Warehouse / Warehouse",),
    ),
    Action(
        "transfers_find",
        "Warehouse / Transfers",
        "Find stock transfers by number and shipment status.",
        FindTransfers,
        (),
        _transfers,
        related_tabs=("Warehouse / Warehouse",),
    ),
    Action(
        "transfers_get",
        "Warehouse / Transfers",
        "Get one stock transfer's status, locations and a page of line IDs and quantities.",
        GetTransfer,
        (),
        _transfer,
    ),
    _documents(
        "purchase_orders_find",
        "Warehouse / Purchase orders",
        "Find purchase orders by number and check receiving status.",
        PurchaseOrder,
        PurchaseOrder.po_number,
        (PurchaseOrder.status, PurchaseOrder.is_archive),
    ),
    _documents(
        "picks_find",
        "Warehouse / Picks",
        "Find warehouse picks by number and check their status.",
        Pick,
        Pick.number,
        (Pick.status, Pick.staging_location_id),
    ),
    Action(
        "till_price_preview",
        "Till",
        "Preview the selling price including VAT for a SKU and quantity, optionally for a customer.",
        PricePreview,
        (TILL_SELL,),
        _price,
    ),
    _directory(
        "customers_find",
        "Sales / Customers",
        "Find an active customer by name to prepare a quote.",
        Customer,
        (Customer.name,),
        (Customer.name,),
    ),
    _documents(
        "quotes_find",
        "Sales / Quotes",
        "Find quotes and their status.",
        Quote,
        Quote.quote_number,
        (Quote.status, Quote.total_inc_vat),
    ),
    _documents(
        "sales_orders_find",
        "Sales / Orders",
        "Find sales orders and check whether stock is outstanding.",
        SalesOrder,
        SalesOrder.so_number,
        (SalesOrder.status, SalesOrder.awaiting_stock, SalesOrder.is_archive),
    ),
    _documents(
        "laybys_find",
        "Sales / Laybys",
        "Find laybys by number, status and due date.",
        Layby,
        Layby.layby_number,
        (Layby.status, Layby.due_date),
    ),
    _documents(
        "returns_find",
        "Sales / Returns",
        "Find merchandise returns and their status.",
        StockReturn,
        StockReturn.return_number,
        (StockReturn.status, StockReturn.invoice_id),
    ),
    _documents(
        "deliveries_find",
        "Sales / Deliveries",
        "Find deliveries, scheduled dates and loading status.",
        Delivery,
        Delivery.delivery_number,
        (Delivery.status, Delivery.delivery_date),
    ),
    _directory(
        "accounts_find",
        "Books / Chart of accounts",
        "Find active ledger accounts by name or account code.",
        Account,
        (Account.code, Account.name, Account.type, Account.is_bank),
        (Account.code, Account.name),
    ),
    _documents(
        "repeating_invoices_find",
        "Books / Repeating invoices",
        "Find recurring invoices by schedule name and check their next issue date.",
        RepeatingInvoice,
        RepeatingInvoice.name,
        (RepeatingInvoice.next_date, RepeatingInvoice.is_active),
    ),
    _documents(
        "journals_find",
        "Books / Journals",
        "Find journals and check their entry date and posting status.",
        JournalEntry,
        JournalEntry.journal_number,
        (JournalEntry.entry_date, JournalEntry.status),
    ),
    _documents(
        "invoices_find",
        "Books / Invoices",
        "Find invoices, due dates and payment status.",
        TaxInvoice,
        TaxInvoice.invoice_number,
        (TaxInvoice.due_date, TaxInvoice.payment_status, TaxInvoice.is_archive),
    ),
    _documents(
        "credit_notes_find",
        "Books / Credit notes",
        "Find credit notes by number and identify the corresponding invoice.",
        CreditNote,
        CreditNote.credit_note_number,
        (CreditNote.invoice_id, CreditNote.issue_date),
    ),
    _documents(
        "bills_find",
        "Books / Bills",
        "Find supplier bills and payment status.",
        Bill,
        Bill.bill_number,
        (Bill.issue_date, Bill.currency, Bill.payment_status, Bill.is_archive),
    ),
    _documents(
        "payments_find",
        "Books / Payments",
        "Find recorded payments and reconciliation status.",
        Payment,
        Payment.payment_number,
        (Payment.direction, Payment.paid_on, Payment.is_reconciled),
    ),
    Action(
        "my_permissions",
        "Admin / My profile",
        "Show your current staff permissions in this business.",
        Arguments,
        (),
        _my_access,
    ),
    _directory(
        "roles_find",
        "Admin / Roles & permissions",
        "Find staff role names and role slugs in this business.",
        Role,
        (Role.name, Role.slug),
        (Role.name, Role.slug),
        permissions=(USERS_MANAGE,),
        active_only=False,
    ),
)
