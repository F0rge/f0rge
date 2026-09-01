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
    auth,
    bank_imports,
    bills,
    contacts,
    credit_notes,
    health,
    invoices,
    locations,
    payments,
    proformas,
    purchase_orders,
    reports,
    skus,
    suppliers,
    transfers,
    users,
)
from app.services.chart_of_accounts import ChartOfAccountsSeedService
from app.services.locations import LocationSeedService
from app.services.users import BootstrapService


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    async with async_session_maker() as session:
        await BootstrapService(session).seed_if_empty()
        await LocationSeedService(session).seed_if_empty()
        await ChartOfAccountsSeedService(session).seed_if_empty()
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
app.include_router(purchase_orders.purchase_orders_router)
app.include_router(purchase_orders.receive_router)
app.include_router(purchase_orders.inventory_router)
app.include_router(transfers.transfers_router)
app.include_router(accounts.accounts_router)
app.include_router(contacts.contacts_router)
app.include_router(invoices.invoices_router)
app.include_router(credit_notes.credit_notes_router)
app.include_router(bills.bills_router)
app.include_router(payments.payments_router)
app.include_router(bank_imports.bank_imports_router)
app.include_router(reports.reports_router)
