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

from app.exceptions import (
    CommsEncryptionUnconfiguredError,
    CommsSmtpFailedError,
    CommsSmtpUnconfiguredError,
    ForbiddenError,
    NiaCapExceededError,
    NiaLlmUnconfiguredError,
)

from app.config import settings
from app.database import default_tenant_sessionmaker
from app.middleware.auth import AuthContextMiddleware
from app.middleware.tenant import TenantContextMiddleware
from app.platform.crud import TenantCRUD
from app.platform.database import PlatformDatabaseUnconfiguredError, platform_sessionmaker
from app.platform.service import decrypt_database_url
from app.tenancy.context import tenant_ctx
from app.tenancy.engines import engine_cache
from app.tenancy.errors import TenantContext
from app.routers import (
    accounts,
    adjustments,
    audit,
    auth,
    bank_imports,
    bank_rules,
    bills,
    books_events,
    books_periods,
    branding,
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
    platform_signup,
    price_lists,
    proformas,
    purchase_orders,
    reorder,
    repeating_invoices,
    returns,
    laybys,
    lookbooks,
    public_lookbooks,
    quotes,
    sales_orders,
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
    whatsapp_webhook,
)
from app.services.nia_schedule import NiaScheduleService
from app.services.tenant_seed import seed_default_dev_extras, seed_tenant_baseline

logger = logging.getLogger(__name__)

TICK_INTERVAL_SECONDS = 60


async def _tenant_context(tenant) -> Optional[TenantContext]:
    if not tenant.database_url_encrypted:
        return None
    return TenantContext(
        id=tenant.id,
        slug=tenant.slug,
        database_url=decrypt_database_url(tenant.database_url_encrypted),
        storage_prefix=tenant.storage_prefix,
    )


async def seed_startup() -> None:
    try:
        maker = platform_sessionmaker()
    except PlatformDatabaseUnconfiguredError:
        logger.warning("single-tenant dev mode")
        async with default_tenant_sessionmaker()() as session:
            await seed_tenant_baseline(session)
            if settings.seed_dev_extras:
                await seed_default_dev_extras(session)
        return
    async with maker() as pdb:
        try:
            tenant = await TenantCRUD(pdb).get_by_slug(settings.default_tenant_slug)
        except Exception:
            logger.warning("platform registry unavailable; skipping startup seed")
            return
    if tenant is None or tenant.status != "ready":
        logger.warning("default tenant not ready; skipping startup seed")
        return
    ctx = await _tenant_context(tenant)
    if ctx is None:
        logger.warning("default tenant has no database url; skipping startup seed")
        return
    token = tenant_ctx.set(ctx)
    try:
        session_maker = await engine_cache.get_sessionmaker(ctx)
        async with session_maker() as session:
            await seed_tenant_baseline(session)
            if settings.seed_dev_extras and tenant.slug == settings.default_tenant_slug:
                await seed_default_dev_extras(session)
    finally:
        tenant_ctx.reset(token)


async def tick_ready_tenants() -> None:
    try:
        maker = platform_sessionmaker()
    except PlatformDatabaseUnconfiguredError:
        try:
            async with default_tenant_sessionmaker()() as session:
                await NiaScheduleService(session).tick_due_tasks()
        except Exception:
            logger.exception("nia schedule tick failed")
        return
    async with maker() as pdb:
        tenants = await TenantCRUD(pdb).list_ready()
    for tenant in tenants:
        ctx = await _tenant_context(tenant)
        if ctx is None:
            continue
        token = tenant_ctx.set(ctx)
        try:
            session_maker = await engine_cache.get_sessionmaker(ctx)
            async with session_maker() as session:
                await NiaScheduleService(session).tick_due_tasks()
        except Exception:
            logger.exception("nia schedule tick failed slug=%s", tenant.slug)
        finally:
            tenant_ctx.reset(token)


async def _nia_schedule_loop(stop: asyncio.Event) -> None:
    while not stop.is_set():
        await tick_ready_tenants()
        try:
            await asyncio.wait_for(stop.wait(), timeout=TICK_INTERVAL_SECONDS)
        except asyncio.TimeoutError:
            continue


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await seed_startup()
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
        await engine_cache.dispose_all()


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
    NiaLlmUnconfiguredError,
    cast(ExceptionHandler, _nia_llm_unconfigured_handler),
)
app.add_exception_handler(
    NiaCapExceededError,
    cast(ExceptionHandler, _nia_cap_exceeded_handler),
)
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

app.add_middleware(AuthContextMiddleware)
app.add_middleware(TenantContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=settings.cors_origin_regex or None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api/v1")
app.include_router(branding.branding_router)
app.include_router(platform_signup.platform_signup_router)
app.include_router(auth.router)
app.include_router(users.users_router)
app.include_router(users.profile_router)
app.include_router(roles.roles_router)
app.include_router(locations.locations_router)
app.include_router(suppliers.suppliers_router)
app.include_router(price_lists.price_lists_router)
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
app.include_router(quotes.quotes_router)
app.include_router(lookbooks.lookbooks_router)
app.include_router(public_lookbooks.public_lookbooks_router)
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
app.include_router(nia.nia_router)
app.include_router(nia_threads.nia_threads_router)
app.include_router(nia_run.nia_run_router)
app.include_router(nia_usage_router.nia_usage_router)
app.include_router(nia_schedule.nia_schedule_router)
