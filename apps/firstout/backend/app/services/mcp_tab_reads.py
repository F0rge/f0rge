"""Sidebar workflows with their own query or projection instead of a document lookup."""

from __future__ import annotations

from dataclasses import asdict
from datetime import date
from uuid import UUID

from pydantic import Field, model_validator
from pydantic_core import to_jsonable_python
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.reorder import ReorderCRUD
from app.models.bank_import import BankImport, BankImportLine
from app.models.books_period import BooksPeriod
from app.models.document_sequence import DocumentSequence
from app.models.mcp_token import McpToken
from app.models.membership import Membership
from app.models.purchase_order import PurchaseOrder, PurchaseOrderStatus
from app.models.team import Team
from app.models.team_settings import TeamSettings
from app.models.user import User
from app.models.vat201_period import Vat201Period
from app.permissions import CATALOGUE_MUTATE, USERS_MANAGE
from app.services.audit_hub import AuditHubService
from app.services.catalogue_csv import INVENTORY_FIELDS, parse_inventory_csv
from app.services.mcp_action_types import Action, Arguments, FindRecords, PageArguments, paged_rows
from app.services.records import RecordsService
from app.services.reports import ReportsService


class InventoryCsv(Arguments):
    csv_text: str = Field(
        min_length=1, max_length=8192, description="Inventory CSV header and sample rows."
    )


class CashReport(Arguments):
    account_id: UUID = Field(description="An active bank ledger account ID from accounts_find.")
    from_date: date
    to_date: date

    @model_validator(mode="after")
    def date_range(self):
        if not 0 <= (self.to_date - self.from_date).days <= 366:
            raise ValueError("Choose a date range of up to one year")
        return self


class SalesHistory(FindRecords):
    customer_id: UUID | None = None
    sku_id: UUID | None = None


async def _check_csv(db: AsyncSession, token: McpToken, args: InventoryCsv) -> dict:
    parsed = parse_inventory_csv(args.csv_text.encode("utf-8"))
    return {
        "rows_checked": parsed.row_count,
        "error_count": len(parsed.errors),
        "first_errors": [
            {
                "row": error.row,
                "fields": [field for field in INVENTORY_FIELDS if field in error.message],
            }
            for error in parsed.errors[:5]
        ],
    }


async def _reorder(db: AsyncSession, token: McpToken, args: PageArguments) -> dict:
    rows = await ReorderCRUD(db).list_below_min(limit=args.limit + 1, offset=args.offset)
    return {
        "items": [to_jsonable_python(asdict(row)) for row in rows[: args.limit]],
        "next_offset": args.offset + args.limit if len(rows) > args.limit else None,
    }


def _purchase_queue(status: PurchaseOrderStatus):
    async def lookup(db: AsyncSession, token: McpToken, args: FindRecords) -> dict:
        po = PurchaseOrder
        stmt = select(po.id, po.po_number, po.status, po.supplier_id).where(
            po.team_id == token.team_id, po.status == status, po.is_archive.is_(False)
        )
        if args.query is not None:
            stmt = stmt.where(po.po_number.icontains(args.query, autoescape=True))
        return await paged_rows(db, stmt.order_by(po.po_number, po.id), args)

    return lookup


async def _history(db: AsyncSession, token: McpToken, args: SalesHistory) -> dict:
    page = await RecordsService(db).sales_history(
        args.page(), customer_id=args.customer_id, sku_id=args.sku_id
    )
    fields = {"kind", "document_id", "document_number", "issue_date", "sku_id", "our_ref", "qty"}
    return {
        "items": [item.model_dump(mode="json", include=fields) for item in page.items],
        "total": page.total,
    }


def _periods(model):
    async def lookup(db: AsyncSession, token: McpToken, args: PageArguments) -> dict:
        return await paged_rows(
            db,
            select(model.id, model.period_from, model.period_to, model.status)
            .where(model.team_id == token.team_id)
            .order_by(model.period_from.desc(), model.id),
            args,
        )

    return lookup


async def _unmatched(db: AsyncSession, token: McpToken, args: PageArguments) -> dict:
    stmt = (
        select(BankImport.account_id, func.count().label("unmatched_lines"))
        .select_from(BankImportLine)
        .join(BankImport, BankImportLine.import_id == BankImport.id)
        .where(
            BankImport.team_id == token.team_id,
            BankImportLine.team_id == token.team_id,
            BankImportLine.matched_payment_id.is_(None),
            BankImportLine.matched_journal_id.is_(None),
        )
        .group_by(BankImport.account_id)
        .order_by(BankImport.account_id)
    )
    return await paged_rows(db, stmt, args)


async def _cash_report(db: AsyncSession, token: McpToken, args: CashReport) -> dict:
    report = await ReportsService(db).cash_summary(
        args.from_date, args.to_date, account_id=args.account_id
    )
    return report.model_dump(mode="json")


async def _organisation(db: AsyncSession, token: McpToken, args: Arguments) -> dict:
    result = await db.execute(select(Team.id, Team.name, Team.slug).where(Team.id == token.team_id))
    return to_jsonable_python(dict(result.mappings().one()))


async def _staff(db: AsyncSession, token: McpToken, args: FindRecords) -> dict:
    role = case((Membership.is_legacy_home, User.role), else_=Membership.role).label("role")
    stmt = (
        select(User.id, User.display_name, role)
        .join(Membership, User.id == Membership.user_id)
        .where(
            Membership.team_id == token.team_id,
            Membership.is_disabled.is_(False),
            User.is_disabled.is_(False),
            User.role != "system",
        )
    )
    if args.query is not None:
        stmt = stmt.where(User.display_name.icontains(args.query, autoescape=True))
    return await paged_rows(db, stmt.order_by(User.display_name, User.id), args)


async def _settings(db: AsyncSession, token: McpToken, args: Arguments) -> dict:
    # SettingsService.get_for_user lazily provisions configuration. Exclude that
    # mutation and all financial account details from this read-only projection.
    result = await db.execute(
        select(
            TeamSettings.trading_name,
            TeamSettings.home_currency,
            TeamSettings.vat_rate,
            TeamSettings.payment_terms_days,
            TeamSettings.default_receive_location_id,
            TeamSettings.default_till_location_id,
            TeamSettings.label_width_mm,
            TeamSettings.label_height_mm,
        ).where(TeamSettings.team_id == token.team_id)
    )
    row = result.mappings().one_or_none()
    return {
        "configured": row is not None,
        "settings": to_jsonable_python(dict(row)) if row else None,
    }


async def _sequences(db: AsyncSession, token: McpToken, args: PageArguments) -> dict:
    stmt = (
        select(DocumentSequence.doc_type, DocumentSequence.prefix, DocumentSequence.padding)
        .where(DocumentSequence.team_id == token.team_id)
        .order_by(DocumentSequence.doc_type)
    )
    return await paged_rows(db, stmt, args)


async def _connection(db: AsyncSession, token: McpToken, args: Arguments) -> dict:
    return {"name": token.name, "expires_at": token.expires_at.isoformat(), "status": token.status}


async def _audit(db: AsyncSession, token: McpToken, args: FindRecords) -> dict:
    page = await AuditHubService(db).list_events(token.user_id, args.page())
    return page.model_dump(
        mode="json",
        include={
            "items": {"__all__": {"at", "actor", "summary", "source", "origin", "operation_id"}},
            "total": True,
        },
    )


TAB_READ_ACTIONS = (
    Action(
        "inventory_import_check_csv",
        "Stock / Import",
        "Check inventory CSV column names and sample row format before uploading in Firstout.",
        InventoryCsv,
        (CATALOGUE_MUTATE,),
        _check_csv,
    ),
    Action(
        "reorder_shortages",
        "Stock / Reorder",
        "List products below their reorder minimum and suggested purchase quantities.",
        PageArguments,
        (),
        _reorder,
    ),
    Action(
        "transit_purchase_orders",
        "Warehouse / Transit",
        "Find open shipments with purchase orders currently on the water.",
        FindRecords,
        (),
        _purchase_queue(PurchaseOrderStatus.ON_WATER),
    ),
    Action(
        "receiving_purchase_orders",
        "Warehouse / Receive",
        "Find landed purchase orders awaiting receipt into the warehouse.",
        FindRecords,
        (),
        _purchase_queue(PurchaseOrderStatus.LANDED),
        related_tabs=("Warehouse / Warehouse",),
    ),
    Action(
        "sales_history_find",
        "Sales / History",
        "Find historical invoice and credit note lines by document, customer or SKU.",
        SalesHistory,
        (),
        _history,
    ),
    Action(
        "bank_unmatched_counts",
        "Books / Bank reconciliation",
        "Count unmatched bank statement lines by bank account.",
        PageArguments,
        (),
        _unmatched,
    ),
    Action(
        "report_cash_summary",
        "Books / Reports",
        "Report cash in, cash out and net cash for one bank account and date range.",
        CashReport,
        (),
        _cash_report,
    ),
    Action(
        "vat201_periods_list",
        "Books / VAT201",
        "List VAT201 periods and their lock status.",
        PageArguments,
        (),
        _periods(Vat201Period),
    ),
    Action(
        "books_periods_list",
        "Books / Books periods",
        "List accounting periods and their lock status.",
        PageArguments,
        (),
        _periods(BooksPeriod),
    ),
    Action(
        "current_business",
        "Admin / Organisation",
        "Identify the business in which this token acts.",
        Arguments,
        (USERS_MANAGE,),
        _organisation,
    ),
    Action(
        "team_members_find",
        "Admin / Team members",
        "Find active staff by display name and see their role in this business.",
        FindRecords,
        (USERS_MANAGE,),
        _staff,
    ),
    Action(
        "business_settings",
        "Admin / Settings directory",
        "Show configured company, currency, tax, receiving, till, payment and label defaults.",
        Arguments,
        (),
        _settings,
        related_tabs=(
            "Admin / Company",
            "Admin / Locations",
            "Admin / Operations",
            "Admin / Labels",
        ),
    ),
    Action(
        "document_number_formats",
        "Admin / Documents",
        "List configured document numbering prefixes and number widths.",
        PageArguments,
        (),
        _sequences,
        related_tabs=("Admin / Settings directory",),
    ),
    Action(
        "current_token",
        "Admin / MCP tokens",
        "Identify the personal token used for this request and when it expires.",
        Arguments,
        (),
        _connection,
        related_tabs=("Admin / Integrations",),
    ),
    Action(
        "audit_events_find",
        "Admin / Audit log",
        "Search the audit log visible to you for users, actions, and MCP operations.",
        FindRecords,
        (),
        _audit,
    ),
)
