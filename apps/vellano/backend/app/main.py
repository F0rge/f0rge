from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from typing import AsyncIterator, Optional, cast

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.types import ExceptionHandler
from f0rge_core.handlers import register_exception_handlers

from app.exceptions import ForbiddenError, NiaCapExceededError, NiaLlmUnconfiguredError

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
    picks,
    proformas,
    purchase_orders,
    reorder,
    repeating_invoices,
    returns,
    laybys,
    nia,
    nia_run,
    nia_schedule,
    nia_threads,
    nia_usage as nia_usage_router,
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
)
from app.services.chart_of_accounts import ChartOfAccountsSeedService
from app.services.locations import LocationSeedService
from app.services.playground_seed import PlaygroundSeedService
from app.services.role_user_seed import RoleUserSeedService
from app.services.roles import RoleSeedService
from app.services.till_seed import TillSeedService
from app.services.nia_schedule import NiaScheduleService
from app.services.users import BootstrapService

logger = logging.getLogger(__name__)

TICK_INTERVAL_SECONDS = 60


async def _nia_schedule_loop(stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            async with async_session_maker() as session:
                await NiaScheduleService(session).tick_due_tasks()
        except Exception:
            logger.exception("nia schedule tick failed")
        try:
            await asyncio.wait_for(stop.wait(), timeout=TICK_INTERVAL_SECONDS)
        except asyncio.TimeoutError:
            continue


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    async with async_session_maker() as session:
        await RoleSeedService(session).seed()
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
    stop = asyncio.Event()
    ticker: Optional[asyncio.Task] = None
    if settings.nia_schedule_ticker:
        ticker = asyncio.create_task(_nia_schedule_loop(stop))
    try:
        yield
    finally:
        stop.set()
        if ticker is not None:
            ticker.cancel()
            with suppress(asyncio.CancelledError):
                await ticker


app = FastAPI(
    title="Vellano API",
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


async def _nia_llm_unconfigured_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, NiaLlmUnconfiguredError)
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": {"code": exc.detail}},
    )


async def _nia_cap_exceeded_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, NiaCapExceededError)
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"detail": {"code": exc.detail}},
    )


app.add_exception_handler(ForbiddenError, cast(ExceptionHandler, _forbidden_handler))
app.add_exception_handler(
    NiaLlmUnconfiguredError,
    cast(ExceptionHandler, _nia_llm_unconfigured_handler),
)
app.add_exception_handler(
    NiaCapExceededError,
    cast(ExceptionHandler, _nia_cap_exceeded_handler),
)

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
app.include_router(roles.roles_router)
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
app.include_router(picks.picks_router)
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
app.include_router(nia.nia_router)
app.include_router(nia_threads.nia_threads_router)
app.include_router(nia_run.nia_run_router)
app.include_router(nia_usage_router.nia_usage_router)
app.include_router(nia_schedule.nia_schedule_router)
