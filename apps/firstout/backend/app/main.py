from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator, cast

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.types import ExceptionHandler
from f0rge_core.handlers import register_exception_handlers

from app.exceptions import (
    CommsEncryptionUnconfiguredError,
    CommsSmtpFailedError,
    CommsSmtpUnconfiguredError,
    ForbiddenError,
)

from app.config import settings
from app.database import async_session_maker
from app.middleware.auth import AuthContextMiddleware
from app.middleware.slow_request import SlowRequestMiddleware
from app.routers import (
    records,
    accounts,
    adjustments,
    audit,
    auth,
    bank_imports,
    bank_rules,
    bills,
    books_events,
    books_periods,
    catalogue_imports,
    category_maps,
    comms,
    customer_portal,
    cost_audit,
    credit_notes,
    customers,
    deliveries,
    health,
    home,
    invoices,
    journal_imports,
    journals,
    locations,
    payments,
    picks,
    price_lists,
    proformas,
    purchase_orders,
    reorder,
    repeating_invoices,
    returns,
    laybys,
    quotes,
    sales_orders,
    ops_commerce,
    storefront_orders,
    reports,
    roles,
    search,
    settings as settings_router,
    skus,
    stocktakes,
    suppliers,
    till,
    transfers,
    users,
    vat201_periods,
    whatsapp_webhook,
)
from app.services.chart_of_accounts import ChartOfAccountsSeedService
from app.services.locations import LocationSeedService
from app.services.playground_seed import PlaygroundSeedService
from app.services.role_user_seed import RoleUserSeedService
from app.services.roles import RoleSeedService
from app.services.till_seed import TillSeedService
from app.services.storefront_system_actor import StorefrontSystemActorService
from app.services.users import BootstrapService


async def seed_boot_fixtures(session: AsyncSession) -> None:
    """Role users, storefront system actor, and Walk-in customer.

    Owner bootstrap, locations, and the chart of accounts stay outside this
    gate. Catalogue refill stays on SEED_PLAYGROUND.
    """
    if not settings.seed_boot_fixtures:
        return
    await RoleUserSeedService(session).seed()
    await StorefrontSystemActorService(session).ensure()
    await TillSeedService(session).seed_if_empty()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    async with async_session_maker() as session:
        await RoleSeedService(session).seed()
        await BootstrapService(session).seed_if_empty()
        await LocationSeedService(session).seed_if_empty()
        await seed_boot_fixtures(session)
        coa = ChartOfAccountsSeedService(session)
        await coa.seed_if_empty()
        await coa.ensure_opening_equity()
        await coa.ensure_customer_deposits()
        await coa.ensure_storefront_gateway_clearing()
        await coa.ensure_category_chart()
        await coa.ensure_bank_accounts()
        await PlaygroundSeedService(session).seed_if_enabled()
    yield


app = FastAPI(
    title="Firstout API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

register_exception_handlers(app)


async def _forbidden_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, ForbiddenError)
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={"detail": exc.detail},
    )


async def _comms_unconfigured_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, (CommsEncryptionUnconfiguredError, CommsSmtpUnconfiguredError))
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": {"code": exc.detail}},
    )


async def _comms_smtp_failed_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, CommsSmtpFailedError)
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY,
        content={"detail": {"code": exc.detail, "message": exc.message}},
    )


app.add_exception_handler(ForbiddenError, cast(ExceptionHandler, _forbidden_handler))
app.add_exception_handler(
    CommsEncryptionUnconfiguredError,
    cast(ExceptionHandler, _comms_unconfigured_handler),
)
app.add_exception_handler(
    CommsSmtpUnconfiguredError,
    cast(ExceptionHandler, _comms_unconfigured_handler),
)
app.add_exception_handler(
    CommsSmtpFailedError,
    cast(ExceptionHandler, _comms_smtp_failed_handler),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(AuthContextMiddleware)
app.add_middleware(SlowRequestMiddleware)

app.include_router(health.router, prefix="/api/v1")
app.include_router(auth.router)
app.include_router(users.users_router)
app.include_router(users.profile_router)
app.include_router(roles.roles_router)
app.include_router(locations.locations_router)
app.include_router(suppliers.suppliers_router)
app.include_router(price_lists.price_lists_router)
app.include_router(proformas.proformas_router)
app.include_router(skus.skus_router)
app.include_router(ops_commerce.router)
app.include_router(storefront_orders.router)
app.include_router(catalogue_imports.catalogue_imports_router)
app.include_router(purchase_orders.purchase_orders_router)
app.include_router(purchase_orders.receive_router)
app.include_router(purchase_orders.inventory_router)
app.include_router(reorder.reorder_router)
app.include_router(transfers.transfers_router)
app.include_router(picks.picks_router)
app.include_router(stocktakes.stocktakes_router)
app.include_router(adjustments.adjustments_router)
app.include_router(returns.returns_router)
app.include_router(deliveries.deliveries_router)
app.include_router(laybys.laybys_router)
app.include_router(quotes.quotes_router)
app.include_router(sales_orders.sales_orders_router)
app.include_router(customer_portal.portal_router)
app.include_router(till.till_router)
app.include_router(accounts.accounts_router)
app.include_router(category_maps.category_maps_router)
app.include_router(customers.customers_router)
app.include_router(invoices.invoices_router)
app.include_router(repeating_invoices.repeating_invoices_router)
app.include_router(journals.journals_router)
app.include_router(journal_imports.journal_imports_router)
app.include_router(credit_notes.credit_notes_router)
app.include_router(bills.bills_router)
app.include_router(payments.payments_router)
app.include_router(books_events.books_events_router)
app.include_router(books_periods.books_periods_router)
app.include_router(audit.audit_router)
app.include_router(bank_imports.bank_imports_router)
app.include_router(bank_rules.bank_rules_router)
app.include_router(reports.reports_router)
app.include_router(vat201_periods.vat201_periods_router)
app.include_router(search.search_router)
app.include_router(home.home_router)
app.include_router(settings_router.settings_router)
app.include_router(comms.comms_router)
app.include_router(whatsapp_webhook.whatsapp_webhook_router)
app.include_router(cost_audit.cost_audit_router)
app.include_router(records.records_router)
