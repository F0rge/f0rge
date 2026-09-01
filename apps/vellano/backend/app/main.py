from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from f0rge_core.handlers import register_exception_handlers

from app.config import settings
from app.database import async_session_maker
from app.middleware.auth import AuthContextMiddleware
from app.routers import (
    accounts,
    adjustments,
    auth,
    bank_imports,
    bank_rules,
    bills,
    books_events,
    catalogue_imports,
    category_maps,
    contacts,
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
    proformas,
    purchase_orders,
    reorder,
    repeating_invoices,
    returns,
    laybys,
    reports,
    search,
    settings as settings_router,
    skus,
    stocktakes,
    suppliers,
    till,
    transfers,
    users,
    vat201_periods,
)
from app.services.chart_of_accounts import ChartOfAccountsSeedService
from app.services.locations import LocationSeedService
from app.services.playground_seed import PlaygroundSeedService
from app.services.role_user_seed import RoleUserSeedService
from app.services.till_seed import TillSeedService
from app.services.users import BootstrapService


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    async with async_session_maker() as session:
        await BootstrapService(session).seed_if_empty()
        await LocationSeedService(session).seed_if_empty()
        await RoleUserSeedService(session).seed()
        coa = ChartOfAccountsSeedService(session)
        await coa.seed_if_empty()
        await coa.ensure_opening_equity()
        await coa.ensure_customer_deposits()
        await coa.ensure_category_chart()
        await coa.ensure_bank_accounts()
        await TillSeedService(session).seed_if_empty()
        await PlaygroundSeedService(session).seed_if_enabled()
    yield


app = FastAPI(
    title="Vellano API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

register_exception_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(AuthContextMiddleware)

app.include_router(health.router, prefix="/api/v1")
app.include_router(auth.router)
app.include_router(users.users_router)
app.include_router(users.profile_router)
app.include_router(locations.locations_router)
app.include_router(suppliers.suppliers_router)
app.include_router(proformas.proformas_router)
app.include_router(skus.skus_router)
app.include_router(catalogue_imports.catalogue_imports_router)
app.include_router(purchase_orders.purchase_orders_router)
app.include_router(purchase_orders.receive_router)
app.include_router(purchase_orders.inventory_router)
app.include_router(reorder.reorder_router)
app.include_router(transfers.transfers_router)
app.include_router(stocktakes.stocktakes_router)
app.include_router(adjustments.adjustments_router)
app.include_router(returns.returns_router)
app.include_router(deliveries.deliveries_router)
app.include_router(laybys.laybys_router)
app.include_router(till.till_router)
app.include_router(accounts.accounts_router)
app.include_router(category_maps.category_maps_router)
app.include_router(contacts.contacts_router)
app.include_router(customers.customers_router)
app.include_router(invoices.invoices_router)
app.include_router(repeating_invoices.repeating_invoices_router)
app.include_router(journals.journals_router)
app.include_router(journal_imports.journal_imports_router)
app.include_router(credit_notes.credit_notes_router)
app.include_router(bills.bills_router)
app.include_router(payments.payments_router)
app.include_router(books_events.books_events_router)
app.include_router(bank_imports.bank_imports_router)
app.include_router(bank_rules.bank_rules_router)
app.include_router(reports.reports_router)
app.include_router(vat201_periods.vat201_periods_router)
app.include_router(search.search_router)
app.include_router(home.home_router)
app.include_router(settings_router.settings_router)
app.include_router(cost_audit.cost_audit_router)
