"""SKU lifecycle through the shared signed workspace against real PostgreSQL."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.inventory import LocationStock
from app.models.sku import Sku
from app.models.sku_bom_line import SkuBomLine
from app.models.team import Team
from tests.test_record_workspace import execute, prepare, query
from tests.test_sku_bom import _sku
from tests.test_purchase_orders import _location_id_by_name


async def archive(client, record, action="archive"):
    prepared = await prepare(client, "skus", ids=[record["id"]], action=action)
    assert prepared["eligible_count"] == 1, prepared
    result = await execute(client, prepared, "skus")
    assert result["succeeded"] == [record["id"]] and not result["failed"], result
    return result


async def test_sku_archive_preserves_stock_identity_and_shared_workspace_restore(
    owner_client, async_db
):
    location = await _location_id_by_name(owner_client, "Bedfordview")
    row = await _sku(
        owner_client,
        "ARCHIVE-STOCK",
        opening_location_id=location,
        opening_qty="1.2500",
        opening_cost="40.00",
    )
    prepared = await prepare(owner_client, "skus", ids=[row["id"]], action="archive")
    assert prepared["eligible_count"] == 1
    assert any("1.25 at Bedfordview" in item for item in prepared["eligible"][0]["warnings"])
    request = uuid.uuid4()
    result = await execute(owner_client, prepared, "skus", request_id=request)
    replay = await execute(owner_client, prepared, "skus", request_id=request)
    assert result["succeeded"] == [row["id"]] and replay["replayed"]
    detail = (await owner_client.get(f"/api/v1/skus/{row['id']}")).json()
    assert detail["is_archived"] and detail["archived_at"] and detail["archived_by_id"]
    assert (
        detail["our_barcode"] == row["our_barcode"] and detail["is_sellable"] == row["is_sellable"]
    )
    active = (await owner_client.get("/api/v1/skus", params={"q": "ARCHIVE-STOCK"})).json()
    assert not active
    past = await query(owner_client, "skus", q="ARCHIVE-STOCK", lifecycle="archived")
    assert past["total"] == 1 and past["counts"]["archived"] >= 1
    assert (
        await owner_client.get("/api/v1/skus", params={"q": "ARCHIVE-STOCK", "lifecycle": "all"})
    ).json()[0]["id"] == row["id"]
    stock = await async_db.scalar(
        select(LocationStock).where(LocationStock.sku_id == uuid.UUID(row["id"]))
    )
    assert stock.on_hand == Decimal("1.2500")
    await archive(owner_client, row, "restore")
    restored = (await owner_client.get(f"/api/v1/skus/{row['id']}")).json()
    assert (
        not restored["is_archived"]
        and restored["archived_at"] is None
        and restored["archived_by_id"] is None
    )
    await async_db.refresh(stock)
    assert stock.on_hand == Decimal("1.2500")


async def test_active_kit_blocks_component_then_restore_requires_active_components(owner_client):
    parent = await _sku(owner_client, "ARCHIVE-KIT")
    child = await _sku(owner_client, "ARCHIVE-COMP")
    response = await owner_client.put(
        f"/api/v1/skus/{parent['id']}/bom",
        json={"lines": [{"component_sku_id": child["id"], "qty": "0.25"}]},
    )
    assert response.status_code == 200
    blocked = await prepare(owner_client, "skus", ids=[child["id"]], action="archive")
    assert (
        blocked["blocked_count"] == 1
        and blocked["blocked"][0]["dependencies"][0]["id"] == parent["id"]
    )
    await archive(owner_client, parent)
    assert not (await owner_client.get(f"/api/v1/skus/{child['id']}")).json()["is_archived"]
    assert Decimal(
        str((await owner_client.get(f"/api/v1/skus/{parent['id']}/bom")).json()[0]["qty"])
    ) == Decimal("0.25")
    await archive(owner_client, child)
    blocked = await prepare(owner_client, "skus", ids=[parent["id"]], action="restore")
    assert (
        blocked["blocked_count"] == 1
        and blocked["blocked"][0]["dependencies"][0]["id"] == child["id"]
    )
    await archive(owner_client, child, "restore")
    await archive(owner_client, parent, "restore")


async def test_archived_sku_edits_photo_recipe_and_delete_are_denied(owner_client):
    row = await _sku(owner_client, "ARCHIVE-READONLY")
    await archive(owner_client, row)
    assert (
        await owner_client.patch(f"/api/v1/skus/{row['id']}", json={"name": "Changed"})
    ).status_code == 409
    assert (
        await owner_client.patch(f"/api/v1/skus/{row['id']}", json={"is_archived": False})
    ).status_code == 422
    assert (
        await owner_client.post(
            f"/api/v1/skus/{row['id']}/photo", files={"photo": ("a.jpg", b"invalid", "image/jpeg")}
        )
    ).status_code == 409
    assert (
        await owner_client.put(f"/api/v1/skus/{row['id']}/bom", json={"lines": []})
    ).status_code == 409
    assert (await owner_client.delete(f"/api/v1/skus/{row['id']}")).status_code == 409


@pytest.mark.parametrize("offer", [False, True])
async def test_online_publication_and_active_offer_block_archive(owner_client, async_db, offer):
    row = await _sku(owner_client, "ARCHIVE-ONLINE")
    sku = await async_db.get(Sku, uuid.UUID(row["id"]))
    if offer:
        sku.made_to_order_capacity = 2
        sku.made_to_order_lead_time_min_days = 7
        sku.made_to_order_lead_time_max_days = 14
        sku.made_to_order_offer_id = uuid.uuid4()
        sku.made_to_order_expires_at = datetime.datetime.now(
            datetime.timezone.utc
        ) + datetime.timedelta(days=1)
    else:
        sku.storefront_published = True
    await async_db.flush()
    prepared = await prepare(owner_client, "skus", ids=[row["id"]], action="archive")
    assert prepared["eligible_count"] == 0 and prepared["blocked_count"] == 1
    assert "online shop" in prepared["blocked"][0]["reason"]
    assert not sku.is_archived


async def test_new_kit_dependency_after_preflight_requires_fresh_preview(owner_client):
    component = await _sku(owner_client, "ARCHIVE-STALE-COMP")
    parent = await _sku(owner_client, "ARCHIVE-STALE-KIT")
    prepared = await prepare(owner_client, "skus", ids=[component["id"]], action="archive")
    assert (
        await owner_client.put(
            f"/api/v1/skus/{parent['id']}/bom",
            json={"lines": [{"component_sku_id": component["id"], "qty": 1}]},
        )
    ).status_code == 200
    result = await execute(owner_client, prepared, "skus")
    assert not result["succeeded"] and "changed after review" in result["failed"][0]["reason"]
    assert not (await owner_client.get(f"/api/v1/skus/{component['id']}")).json()["is_archived"]


async def test_stock_changed_after_preflight_is_not_silently_acknowledged(owner_client, async_db):
    location = await _location_id_by_name(owner_client, "Bedfordview")
    row = await _sku(
        owner_client,
        "ARCHIVE-STALE-STOCK",
        opening_location_id=location,
        opening_qty="1.25",
        opening_cost="40",
    )
    prepared = await prepare(owner_client, "skus", ids=[row["id"]], action="archive")
    stock = await async_db.scalar(
        select(LocationStock).where(LocationStock.sku_id == uuid.UUID(row["id"]))
    )
    stock.on_hand = Decimal("2.5001")
    await async_db.flush()
    result = await execute(owner_client, prepared, "skus")
    assert not result["succeeded"] and "changed after review" in result["failed"][0]["reason"]
    fresh = await prepare(owner_client, "skus", ids=[row["id"]], action="archive")
    assert any("2.5001 at Bedfordview" in item for item in fresh["eligible"][0]["warnings"])


async def test_bom_cannot_add_archived_component_or_create_nested_kit(owner_client):
    parent = await _sku(owner_client, "ARCHIVE-NEW-PARENT")
    component = await _sku(owner_client, "ARCHIVE-NEW-COMP")
    third = await _sku(owner_client, "ARCHIVE-NEW-THIRD")
    await archive(owner_client, component)
    response = await owner_client.put(
        f"/api/v1/skus/{parent['id']}/bom",
        json={"lines": [{"component_sku_id": component["id"], "qty": 1}]},
    )
    assert response.status_code == 409
    await archive(owner_client, component, "restore")
    assert (
        await owner_client.put(
            f"/api/v1/skus/{component['id']}/bom",
            json={"lines": [{"component_sku_id": third["id"], "qty": 1}]},
        )
    ).status_code == 200
    assert (
        await owner_client.put(
            f"/api/v1/skus/{parent['id']}/bom",
            json={"lines": [{"component_sku_id": component["id"], "qty": 1}]},
        )
    ).status_code == 400


async def test_imported_nested_graph_fails_closed_without_touching_recipes(owner_client, async_db):
    rows = [await _sku(owner_client, f"ARCHIVE-CORRUPT-{i}") for i in range(3)]
    async_db.add_all(
        [
            SkuBomLine(
                parent_sku_id=uuid.UUID(rows[0]["id"]),
                component_sku_id=uuid.UUID(rows[1]["id"]),
                qty=1,
            ),
            SkuBomLine(
                parent_sku_id=uuid.UUID(rows[1]["id"]),
                component_sku_id=uuid.UUID(rows[2]["id"]),
                qty=1,
            ),
        ]
    )
    await async_db.flush()
    prepared = await prepare(owner_client, "skus", ids=[rows[0]["id"]], action="archive")
    assert prepared["blocked_count"] == 1 and "Nested or cyclic" in prepared["blocked"][0]["reason"]
    assert len((await owner_client.get(f"/api/v1/skus/{rows[0]['id']}/bom")).json()) == 1


async def test_foreign_sku_is_unavailable_to_workspace(owner_client, async_db):
    team = Team(name="Other archive org", slug=f"sku-archive-{uuid.uuid4().hex}")
    async_db.add(team)
    await async_db.flush()
    sku = Sku(
        team_id=team.id,
        our_ref="ARCHIVE-FOREIGN",
        our_barcode="ARCHIVE-FOREIGN",
        name="Other org private SKU",
        design="foreign",
        fabric="foreign",
    )
    async_db.add(sku)
    await async_db.flush()
    result = await query(owner_client, "skus", q="ARCHIVE-FOREIGN", lifecycle="all")
    assert not result["items"]
    prepared = await prepare(owner_client, "skus", ids=[str(sku.id)], action="archive")
    assert (
        prepared["blocked_count"] == 1 and prepared["blocked"][0]["label"] == "Unavailable record"
    )
    assert "private SKU" not in str(prepared)


async def test_archive_stock_warning_does_not_net_positive_and_negative_locations(
    owner_client, async_db
):
    row = await _sku(owner_client, "ARCHIVE-NO-NET")
    first = await _location_id_by_name(owner_client, "Bedfordview")
    second = await _location_id_by_name(owner_client, "Kramerville")
    async_db.add_all(
        [
            LocationStock(
                sku_id=uuid.UUID(row["id"]), location_id=uuid.UUID(first), on_hand=Decimal("1.2501")
            ),
            LocationStock(
                sku_id=uuid.UUID(row["id"]),
                location_id=uuid.UUID(second),
                on_hand=Decimal("-1.2501"),
            ),
        ]
    )
    await async_db.flush()
    prepared = await prepare(owner_client, "skus", ids=[row["id"]], action="archive")
    warnings = prepared["eligible"][0]["warnings"]
    assert any("1.2501 at Bedfordview" in item for item in warnings)
    assert any("-1.2501 at Kramerville" in item for item in warnings)
    await execute(owner_client, prepared, "skus")
    quantities = list(
        (
            await async_db.scalars(
                select(LocationStock.on_hand).where(LocationStock.sku_id == uuid.UUID(row["id"]))
            )
        ).all()
    )
    assert sorted(quantities) == [Decimal("-1.2501"), Decimal("1.2501")]


async def test_sku_workspace_permissions_and_cost_masking(owner_client):
    from tests.conftest import authenticate_as, create_test_staff

    location = await _location_id_by_name(owner_client, "Bedfordview")
    row = await _sku(
        owner_client,
        "ARCHIVE-COST",
        opening_location_id=location,
        opening_qty=1,
        opening_cost="123.45",
    )
    prepared = await prepare(owner_client, "skus", ids=[row["id"]], action="archive")
    await create_test_staff(owner_client, email="archive-warehouse@example.com", role="warehouse")
    await authenticate_as(owner_client, "archive-warehouse@example.com")
    result = await query(owner_client, "skus", q="ARCHIVE-COST")
    assert result["items"][0]["average_unit_cost_zar"] is None
    assert result["items"][0]["last_landed_cost_zar"] is None
    denied = await owner_client.post(
        "/api/v1/record-workspaces/skus/preflight", json={"ids": [row["id"]], "action": "archive"}
    )
    assert denied.status_code == 403
    stolen = await owner_client.post(
        "/api/v1/record-workspaces/skus/execute",
        json={"preflight_token": prepared["preflight_token"], "request_id": str(uuid.uuid4())},
    )
    assert stolen.status_code == 403


async def test_archive_warns_about_open_quote_and_preserves_it(owner_client):
    row = await _sku(owner_client, "ARCHIVE-QUOTE", retail_ex_vat="100")
    customer = (
        await owner_client.post("/api/v1/customers", json={"name": "Archive quote fixture"})
    ).json()
    quoted = await owner_client.post(
        "/api/v1/quotes",
        json={"customer_id": customer["id"], "lines": [{"sku_id": row["id"], "qty": 2}]},
    )
    assert quoted.status_code == 201, quoted.text
    prepared = await prepare(owner_client, "skus", ids=[row["id"]], action="archive")
    assert any("1 open quotes" in item for item in prepared["eligible"][0]["warnings"])
    await execute(owner_client, prepared, "skus")
    old = await owner_client.get(f"/api/v1/quotes/{quoted.json()['id']}")
    assert old.status_code == 200 and old.json()["lines"][0]["qty"] == 2


async def test_expired_mto_and_not_sellable_flag_remain_unchanged_on_restore(
    owner_client, async_db
):
    row = await _sku(owner_client, "ARCHIVE-EXPIRED")
    sku = await async_db.get(Sku, uuid.UUID(row["id"]))
    sku.is_sellable = False
    sku.made_to_order_capacity = 2
    sku.made_to_order_lead_time_min_days = 7
    sku.made_to_order_lead_time_max_days = 14
    offer = uuid.uuid4()
    expiry = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)
    sku.made_to_order_offer_id, sku.made_to_order_expires_at = offer, expiry
    await async_db.flush()
    await archive(owner_client, row)
    await archive(owner_client, row, "restore")
    await async_db.refresh(sku)
    assert not sku.is_sellable and not sku.storefront_published
    assert sku.made_to_order_offer_id == offer and sku.made_to_order_expires_at == expiry


async def test_archive_serializes_bom_insertion_and_refreshes_cached_sku(async_engine):
    """A recipe writer that waited for archive cannot reuse its cached active flag."""
    import asyncio

    from sqlalchemy import delete
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.config import settings
    from app.database import TenantSession
    from app.models.user import User
    from app.schemas.sku_bom import SkuBomReplace
    from app.services.sku_archive import SkuArchiveService
    from app.services.sku_bom import SkuBomService
    from f0rge_core.exceptions import ConflictError
    from f0rge_db.crud import unit_of_work

    maker = async_sessionmaker(
        async_engine, expire_on_commit=False, sync_session_class=TenantSession
    )
    async with maker() as setup:
        actor = await setup.scalar(select(User.id).where(User.email == settings.seed_owner_email))
        suffix = uuid.uuid4().hex
        records = [
            Sku(
                our_ref=f"RACE-{i}-{suffix}",
                our_barcode=f"RACE-{i}-{suffix}",
                name="Archive lock fixture",
                design=f"RACE-{i}-{suffix}",
                fabric="-",
            )
            for i in range(2)
        ]
        async with unit_of_work(setup):
            setup.add_all(records)
            await setup.flush()
        parent_id, component_id = [record.id for record in records]
    try:
        async with maker() as archiver, maker() as writer:
            cached = await writer.get(Sku, component_id)
            assert not cached.is_archived
            await SkuArchiveService(archiver).lock_skus([component_id])
            started = asyncio.Event()

            async def add_recipe():
                started.set()
                try:
                    await SkuBomService(writer).replace(
                        parent_id,
                        SkuBomReplace.model_validate(
                            {"lines": [{"component_sku_id": component_id, "qty": 1}]}
                        ),
                    )
                finally:
                    await writer.rollback()

            waiting = asyncio.create_task(add_recipe())
            await started.wait()
            await asyncio.sleep(0.05)
            assert not waiting.done()
            await SkuArchiveService(archiver).set_archived(component_id, True, actor)
            with pytest.raises(ConflictError, match="Restore the component"):
                await asyncio.wait_for(waiting, 10)
        async with maker() as check:
            assert (await check.get(Sku, component_id)).is_archived
            assert not (
                await check.scalars(select(SkuBomLine).where(SkuBomLine.parent_sku_id == parent_id))
            ).all()
    finally:
        async with maker() as cleanup:
            async with unit_of_work(cleanup):
                await cleanup.execute(
                    delete(SkuBomLine).where(SkuBomLine.parent_sku_id == parent_id)
                )
                await cleanup.execute(delete(Sku).where(Sku.id.in_([parent_id, component_id])))


async def test_imported_three_node_cycle_can_be_repaired_stepwise(owner_client, async_db):
    rows = [await _sku(owner_client, f"ARCHIVE-REPAIR-CYCLE-{i}") for i in range(3)]
    async_db.add_all(
        [
            SkuBomLine(
                parent_sku_id=uuid.UUID(rows[i]["id"]),
                component_sku_id=uuid.UUID(rows[(i + 1) % 3]["id"]),
                qty=1,
            )
            for i in range(3)
        ]
    )
    await async_db.flush()
    blocked = await prepare(owner_client, "skus", ids=[rows[0]["id"]], action="archive")
    assert blocked["blocked_count"] == 1 and "Nested or cyclic" in blocked["blocked"][0]["reason"]
    first = await owner_client.put(f"/api/v1/skus/{rows[0]['id']}/bom", json={"lines": []})
    assert first.status_code == 200, first.text
    assert first.json() == []
    # B -> C -> A is still a nested chain, so archival stays blocked until the next repair.
    still_blocked = await prepare(owner_client, "skus", ids=[rows[1]["id"]], action="archive")
    assert still_blocked["blocked_count"] == 1
    second = await owner_client.put(f"/api/v1/skus/{rows[1]['id']}/bom", json={"lines": []})
    assert second.status_code == 200, second.text
    # Only C -> A remains. C can now be archived without deleting that valid recipe.
    await archive(owner_client, rows[2])
    remaining = (await owner_client.get(f"/api/v1/skus/{rows[2]['id']}/bom")).json()
    assert remaining[0]["component_sku_id"] == rows[0]["id"]


async def test_invalid_graph_repair_allows_only_removing_existing_dependencies(
    owner_client, async_db
):
    rows = [await _sku(owner_client, f"ARCHIVE-REPAIR-SUBSET-{i}") for i in range(4)]
    async_db.add_all(
        [
            SkuBomLine(
                parent_sku_id=uuid.UUID(rows[0]["id"]),
                component_sku_id=uuid.UUID(rows[1]["id"]),
                qty=1,
            ),
            SkuBomLine(
                parent_sku_id=uuid.UUID(rows[0]["id"]),
                component_sku_id=uuid.UUID(rows[2]["id"]),
                qty=1,
            ),
            SkuBomLine(
                parent_sku_id=uuid.UUID(rows[1]["id"]),
                component_sku_id=uuid.UUID(rows[0]["id"]),
                qty=1,
            ),
        ]
    )
    await async_db.flush()
    url = f"/api/v1/skus/{rows[0]['id']}/bom"
    added = await owner_client.put(
        url,
        json={"lines": [{"component_sku_id": rows[3]["id"], "qty": 1}]},
    )
    assert added.status_code in (400, 409), added.text
    increased = await owner_client.put(
        url, json={"lines": [{"component_sku_id": rows[1]["id"], "qty": 2}]}
    )
    assert increased.status_code in (400, 409), increased.text
    # Removing A -> C may retain the existing invalid A -> B edge during stepwise repair.
    subset = await owner_client.put(
        url, json={"lines": [{"component_sku_id": rows[1]["id"], "qty": 1}]}
    )
    assert subset.status_code == 200, subset.text
    assert len(subset.json()) == 1 and subset.json()[0]["component_sku_id"] == rows[1]["id"]
    still_blocked = await prepare(owner_client, "skus", ids=[rows[0]["id"]], action="archive")
    assert still_blocked["blocked_count"] == 1
    cleared = await owner_client.put(url, json={"lines": []})
    assert cleared.status_code == 200, cleared.text
