from __future__ import annotations

import uuid

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.user import UserCRUD
from app.database import get_db
from app.middleware.auth import get_current_user_id
from app.models.user import UserRole
from app.services.auth import AuthService
from app.services.bills import BillService
from app.services.contacts import ContactService
from app.services.credit_notes import CreditNoteService
from app.services.customers_crm import CustomersCrmService
from app.services.accounts import AccountService
from app.services.cost_audit import CostAuditService
from app.services.home import HomeService
from app.services.inventory import InventoryService
from app.services.invoices import InvoiceService
from app.services.repeating_invoices import RepeatingInvoiceService
from app.services.journal_imports import JournalImportService
from app.services.journals import JournalService
from app.services.locations import LocationService
from app.services.payments import PaymentService
from app.services.bank_imports import BankImportService
from app.services.bank_rules import BankRuleService
from app.services.catalogue_imports import CatalogueImportService
from app.services.category_maps import CategoryMapService
from app.services.reports import ReportsService
from app.services.search import SearchService
from app.services.settings import SettingsService
from app.services.proformas import ProformaService
from app.services.purchase_orders import PurchaseOrderService
from app.services.reorder import ReorderService
from app.services.skus import SkuService
from app.services.stock_adjustments import StockAdjustmentService
from app.services.laybys import LaybysService
from app.services.deliveries import DeliveriesService
from app.services.stock_returns import StockReturnsService
from app.services.stocktakes import StocktakeService
from app.services.suppliers import SupplierService
from app.services.transfers import TransferService
from app.services.till_orchestrator import TillOrchestrator
from app.services.users import BootstrapService, ProfileService, UserService
from app.services.vat201_periods import Vat201PeriodService


def get_auth_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    return AuthService(db)


def get_user_service(db: AsyncSession = Depends(get_db)) -> UserService:
    return UserService(db)


def get_profile_service(db: AsyncSession = Depends(get_db)) -> ProfileService:
    return ProfileService(db)


def get_bootstrap_service(db: AsyncSession = Depends(get_db)) -> BootstrapService:
    return BootstrapService(db)


def get_location_service(db: AsyncSession = Depends(get_db)) -> LocationService:
    return LocationService(db)


def get_supplier_service(db: AsyncSession = Depends(get_db)) -> SupplierService:
    return SupplierService(db)


def get_proforma_service(db: AsyncSession = Depends(get_db)) -> ProformaService:
    return ProformaService(db)


def get_sku_service(db: AsyncSession = Depends(get_db)) -> SkuService:
    return SkuService(db)


def get_purchase_order_service(db: AsyncSession = Depends(get_db)) -> PurchaseOrderService:
    return PurchaseOrderService(db)


def get_reorder_service(db: AsyncSession = Depends(get_db)) -> ReorderService:
    return ReorderService(db)


def get_inventory_service(db: AsyncSession = Depends(get_db)) -> InventoryService:
    return InventoryService(db)


def get_home_service(db: AsyncSession = Depends(get_db)) -> HomeService:
    return HomeService(db)


def get_search_service(db: AsyncSession = Depends(get_db)) -> SearchService:
    return SearchService(db)


def get_settings_service(db: AsyncSession = Depends(get_db)) -> SettingsService:
    return SettingsService(db)


def get_cost_audit_service(db: AsyncSession = Depends(get_db)) -> CostAuditService:
    return CostAuditService(db)


def get_account_service(db: AsyncSession = Depends(get_db)) -> AccountService:
    return AccountService(db)


def get_category_map_service(db: AsyncSession = Depends(get_db)) -> CategoryMapService:
    return CategoryMapService(db)


def get_contact_service(db: AsyncSession = Depends(get_db)) -> ContactService:
    return ContactService(db)


def get_customers_crm_service(db: AsyncSession = Depends(get_db)) -> CustomersCrmService:
    return CustomersCrmService(db)


def get_invoice_service(db: AsyncSession = Depends(get_db)) -> InvoiceService:
    return InvoiceService(db)


def get_repeating_invoice_service(
    db: AsyncSession = Depends(get_db),
) -> RepeatingInvoiceService:
    return RepeatingInvoiceService(db)


def get_journal_service(db: AsyncSession = Depends(get_db)) -> JournalService:
    return JournalService(db)


def get_journal_import_service(
    db: AsyncSession = Depends(get_db),
) -> JournalImportService:
    return JournalImportService(db)


def get_credit_note_service(db: AsyncSession = Depends(get_db)) -> CreditNoteService:
    return CreditNoteService(db)


def get_bill_service(db: AsyncSession = Depends(get_db)) -> BillService:
    return BillService(db)


def get_payment_service(db: AsyncSession = Depends(get_db)) -> PaymentService:
    return PaymentService(db)


def get_bank_import_service(db: AsyncSession = Depends(get_db)) -> BankImportService:
    return BankImportService(db)


def get_bank_rule_service(db: AsyncSession = Depends(get_db)) -> BankRuleService:
    return BankRuleService(db)


def get_catalogue_import_service(
    db: AsyncSession = Depends(get_db),
) -> CatalogueImportService:
    return CatalogueImportService(db)


def get_reports_service(db: AsyncSession = Depends(get_db)) -> ReportsService:
    return ReportsService(db)


def get_vat201_period_service(db: AsyncSession = Depends(get_db)) -> Vat201PeriodService:
    return Vat201PeriodService(db)


def get_transfer_service(db: AsyncSession = Depends(get_db)) -> TransferService:
    return TransferService(db)


def get_stocktake_service(db: AsyncSession = Depends(get_db)) -> StocktakeService:
    return StocktakeService(db)


def get_adjustment_service(db: AsyncSession = Depends(get_db)) -> StockAdjustmentService:
    return StockAdjustmentService(db)


def get_stock_returns_service(db: AsyncSession = Depends(get_db)) -> StockReturnsService:
    return StockReturnsService(db)


def get_deliveries_service(db: AsyncSession = Depends(get_db)) -> DeliveriesService:
    return DeliveriesService(db)


def get_layby_service(db: AsyncSession = Depends(get_db)) -> LaybysService:
    return LaybysService(db)


def get_till_orchestrator(db: AsyncSession = Depends(get_db)) -> TillOrchestrator:
    return TillOrchestrator(db)


async def require_till(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> uuid.UUID:
    user = await UserCRUD(db).get_by_id(user_id)
    if user is None or user.role not in (UserRole.OWNER, UserRole.TILL):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner or till access required",
        )
    return user_id


async def require_owner(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> uuid.UUID:
    user = await UserCRUD(db).get_by_id(user_id)
    if user is None or user.role != UserRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner access required",
        )
    return user_id


async def require_location_mutate(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> uuid.UUID:
    user = await UserCRUD(db).get_by_id(user_id)
    if user is None or user.role not in (UserRole.OWNER, UserRole.WAREHOUSE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner or warehouse access required",
        )
    return user_id


async def require_catalogue_mutate(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> uuid.UUID:
    user = await UserCRUD(db).get_by_id(user_id)
    if user is None or user.role not in (UserRole.OWNER, UserRole.BUYER):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner or buyer access required",
        )
    return user_id


async def require_returns_mutate(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> uuid.UUID:
    user = await UserCRUD(db).get_by_id(user_id)
    if user is None or user.role not in (UserRole.OWNER, UserRole.WAREHOUSE, UserRole.TILL):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner, warehouse, or till access required",
        )
    return user_id


async def require_deliveries_mutate(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> uuid.UUID:
    user = await UserCRUD(db).get_by_id(user_id)
    if user is None or user.role not in (UserRole.OWNER, UserRole.WAREHOUSE, UserRole.TILL):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner, warehouse, or till access required",
        )
    return user_id


async def require_receive(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> uuid.UUID:
    user = await UserCRUD(db).get_by_id(user_id)
    if user is None or user.role not in (UserRole.OWNER, UserRole.WAREHOUSE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner or warehouse access required",
        )
    return user_id


async def require_transfer(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> uuid.UUID:
    user = await UserCRUD(db).get_by_id(user_id)
    if user is None or user.role not in (UserRole.OWNER, UserRole.WAREHOUSE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner or warehouse access required",
        )
    return user_id


async def require_books_mutate(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> uuid.UUID:
    user = await UserCRUD(db).get_by_id(user_id)
    if user is None or user.role not in (UserRole.OWNER, UserRole.BOOKS):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner or books access required",
        )
    return user_id


async def require_customers_mutate(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> uuid.UUID:
    user = await UserCRUD(db).get_by_id(user_id)
    if user is None or user.role not in (UserRole.OWNER, UserRole.BOOKS, UserRole.TILL):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner, books, or till access required",
        )
    return user_id


async def require_cost_audit_view(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> uuid.UUID:
    user = await UserCRUD(db).get_by_id(user_id)
    if user is None or user.role not in (
        UserRole.OWNER,
        UserRole.BOOKS,
        UserRole.BUYER,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner, books, or buyer access required",
        )
    return user_id
