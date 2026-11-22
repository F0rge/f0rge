"""Real request sessions must revalidate after independently committed setup writes."""

from __future__ import annotations

import asyncio
import uuid
from contextlib import asynccontextmanager

from sqlalchemy import event, func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.util import await_only

from app.database import Base, TenantSession
from app.models.customer import Customer
from app.models.membership import Membership
from app.models.purchase_order import PoLine, PurchaseOrder
from app.models.sku import Sku
from app.models.sku_supplier_price import SkuSupplierPrice
from app.models.supplier import Supplier
from app.models.team import Team
from app.models.team_settings import TeamSettings
from app.models.user import User
from app.schemas.purchase_order import PoLineSkuCreate, PurchaseOrderCreate
from app.services.chart_of_accounts import ChartOfAccountsSeedService
from app.services.document_numbering import DocumentNumberingService
from app.services.purchase_orders import PurchaseOrderService
from app.services.sku_archive import SkuArchiveService
from f0rge_core.exceptions import ValidationError
from f0rge_db.organisation import tenant_id_ctx


@asynccontextmanager
async def isolated_requests(database_url):
    """A private database gives each race absent settings and independent commits."""
    engine = create_async_engine(database_url)
    maker = async_sessionmaker(engine, expire_on_commit=False, sync_session_class=TenantSession)
    team_id, actor_id, customer_id, supplier_id, sku_id = [uuid.uuid4() for _ in range(5)]
    token = tenant_id_ctx.set(team_id)
    try:
        async with engine.begin() as connection:
            await connection.execute(text("CREATE EXTENSION IF NOT EXISTS citext"))
            await connection.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
            await connection.run_sync(Base.metadata.create_all)
        async with maker() as setup:
            setup.add(Team(id=team_id, name="Archive race tenant", slug="archive-race"))
            await setup.flush()
            setup.add(
                User(
                    id=actor_id,
                    team_id=team_id,
                    email="race@example.com",
                    password_hash="unused",
                    role="owner",
                )
            )
            await setup.flush()
            setup.add_all(
                [
                    Membership(
                        user_id=actor_id, team_id=team_id, role="owner", is_legacy_home=True
                    ),
                    Customer(id=customer_id, name="Archive race customer"),
                    Supplier(id=supplier_id, name="Archive race supplier", default_currency="ZAR"),
                    Sku(
                        id=sku_id,
                        our_ref="RACE-EXISTING",
                        our_barcode="RACE-EXISTING",
                        name="Archive race product",
                        design="RACE",
                        fabric="-",
                        retail_ex_vat=100,
                    ),
                ]
            )
            await setup.commit()
            await ChartOfAccountsSeedService(setup).seed_if_empty()
            await DocumentNumberingService(setup).ensure_all_for_team(team_id)
            await setup.commit()
            assert await setup.scalar(select(TeamSettings.id)) is None
        yield (
            maker,
            {
                "team": team_id,
                "actor": actor_id,
                "customer": customer_id,
                "supplier": supplier_id,
                "sku": sku_id,
            },
        )
    finally:
        tenant_id_ctx.reset(token)
        await engine.dispose()


def pause_actual_commit(session, matches, observed, resume):
    """Schedule a competing request at a real DB commit, without replacing services.

    SQLAlchemy's async bridge permits event listeners to yield. The listener only
    controls scheduling: both requests still execute their actual SQL and services.
    """
    paused = False

    def committed(sync_session):
        nonlocal paused
        if not paused and any(matches(row) for row in sync_session.identity_map.values()):
            paused = True
            observed.set()
            await_only(resume.wait())

    event.listen(session.sync_session, "after_commit", committed)
    return committed


# Invoices no longer create team settings on first use (pricing reads them), so only a
# purchase order commits settings before its SKU validation.
async def test_first_settings_commit_precedes_archived_sku_validation(second_postgres_url):
    async with isolated_requests(second_postgres_url) as (maker, ids):
        async with maker() as writer, maker() as archiver:
            observed, resume = asyncio.Event(), asyncio.Event()
            listener = pause_actual_commit(
                writer, lambda row: isinstance(row, TeamSettings), observed, resume
            )

            async def archive_after_settings_commit():
                await observed.wait()
                try:
                    await SkuArchiveService(archiver).set_archived(ids["sku"], True, ids["actor"])
                finally:
                    resume.set()

            async def create_document():
                try:
                    return await PurchaseOrderService(writer).create(
                        PurchaseOrderCreate.model_validate(
                            {
                                "supplier_id": ids["supplier"],
                                "lines": [
                                    {"sku_id": ids["sku"], "qty": 1, "factory_unit_amount": "10"}
                                ],
                            }
                        ),
                        ids["actor"],
                    )
                except ValidationError as error:
                    return error
                finally:
                    await writer.rollback()

            writing = asyncio.create_task(create_document())
            archiving = asyncio.create_task(archive_after_settings_commit())
            try:
                result, _ = await asyncio.wait_for(asyncio.gather(writing, archiving), 15)
                assert isinstance(result, ValidationError), (
                    "A SKU archived at the setup commit must not enter new business"
                )
                assert "Restore SKU" in result.detail
            finally:
                resume.set()
                for task in (writing, archiving):
                    if not task.done():
                        task.cancel()
                await asyncio.gather(writing, archiving, return_exceptions=True)
                event.remove(writer.sync_session, "after_commit", listener)
        async with maker() as check:
            assert (await check.get(Sku, ids["sku"])).is_archived
            assert await check.scalar(select(TeamSettings.id)) is not None
            assert await check.scalar(select(func.count()).select_from(PurchaseOrder)) == 0


async def test_new_po_sku_is_revalidated_after_creation_commit(second_postgres_url):
    async with isolated_requests(second_postgres_url) as (maker, ids):
        async with maker() as setup:
            pending = await PurchaseOrderService(setup).create(
                PurchaseOrderCreate.model_validate(
                    {
                        "supplier_id": ids["supplier"],
                        "submit_for_approval": True,
                        "lines": [
                            {
                                "description": "Unmatched product",
                                "qty": 1,
                                "factory_unit_amount": "10",
                            }
                        ],
                    }
                ),
                ids["actor"],
            )
            po_id, line_id = pending.id, pending.lines[0].id
        async with maker() as writer, maker() as archiver:
            observed, resume = asyncio.Event(), asyncio.Event()
            new_id = []

            def created_sku(row):
                if isinstance(row, Sku) and row.our_ref == "RACE-NEW-ATTACHMENT":
                    new_id.append(row.id)
                    return True
                return False

            listener = pause_actual_commit(writer, created_sku, observed, resume)

            async def archive_created_sku():
                await observed.wait()
                try:
                    await SkuArchiveService(archiver).set_archived(new_id[0], True, ids["actor"])
                finally:
                    resume.set()

            async def attach_created_sku():
                try:
                    return await PurchaseOrderService(writer).create_line_sku(
                        po_id,
                        line_id,
                        PoLineSkuCreate.model_validate(
                            {
                                "our_ref": "RACE-NEW-ATTACHMENT",
                                "our_barcode": "RACE-NEW-ATTACHMENT",
                                "name": "New archived product",
                                "design": "NEW-RACE",
                                "fabric": "-",
                            }
                        ),
                        ids["actor"],
                    )
                except ValidationError as error:
                    return error
                finally:
                    await writer.rollback()

            writing = asyncio.create_task(attach_created_sku())
            archiving = asyncio.create_task(archive_created_sku())
            try:
                result, _ = await asyncio.wait_for(asyncio.gather(writing, archiving), 15)
                assert isinstance(result, ValidationError), (
                    "An archived new SKU must not be attached after its creation commit"
                )
                assert "Restore SKU" in result.detail
            finally:
                resume.set()
                for task in (writing, archiving):
                    if not task.done():
                        task.cancel()
                await asyncio.gather(writing, archiving, return_exceptions=True)
                event.remove(writer.sync_session, "after_commit", listener)
        async with maker() as check:
            assert (await check.get(PoLine, line_id)).sku_id is None
            sku = await check.get(Sku, new_id[0])
            assert sku.is_archived and sku.preferred_supplier_id is None
            assert (
                await check.scalar(
                    select(SkuSupplierPrice.id).where(SkuSupplierPrice.sku_id == sku.id)
                )
                is None
            )
