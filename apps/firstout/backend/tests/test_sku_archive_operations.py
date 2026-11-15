"""Archived catalogue entries keep physical records but cannot start new business."""

from __future__ import annotations

import uuid
import datetime

from decimal import Decimal

from sqlalchemy import select

from app.models.sku import Sku
from app.models.sku_bom_line import SkuBomLine
from app.services.cin7_import.load import run_import
from tests.test_cin7_import import _fixture_dir, _write_csv
from tests.test_laybys import _layby_payload
from tests.test_purchase_orders import _create_supplier, _location_id_by_name
from tests.test_quotes import _named_customer
from tests.test_sku_bom import _sku


async def archive_fixture(db, sku_id):
    sku = await db.get(Sku, uuid.UUID(sku_id))
    sku.is_archived = True
    sku.archived_at = datetime.datetime.utcnow()
    await db.flush()


async def test_archived_sku_cannot_start_new_business(owner_client, async_db):
    client = owner_client
    sku = await _sku(client, "ARC-NEW", retail_ex_vat="1000")
    customer = await _named_customer(client, "Archived business buyer")
    supplier = await _create_supplier(client, "Archived business vendor")
    location = await _location_id_by_name(client, "Bedfordview")
    await archive_fixture(async_db, sku["id"])
    line = {"sku_id": sku["id"], "qty": 1}
    requests = [
        ("/quotes", {"customer_id": customer, "lines": [line]}),
        ("/laybys", _layby_payload(customer, location, sku["id"], hold_stock=False)),
        (
            "/purchase-orders",
            {"supplier_id": supplier, "lines": [{**line, "factory_unit_amount": "10"}]},
        ),
        ("/picks", {"sku_id": sku["id"], "qty": 1}),
        ("/till/sales", {"location_id": location, "tender": "cash", "lines": [line]}),
    ]
    for path, body in requests:
        response = await client.post("/api/v1" + path, json=body)
        assert response.status_code == 400, (path, response.text)
        assert "Restore SKU" in response.text


async def test_existing_archived_quote_can_finish_without_increase_or_copy(owner_client, async_db):
    client = owner_client
    sku = await _sku(client, "ARC-QUOTE", retail_ex_vat="1000")
    customer = await _named_customer(client, "Archived quote buyer")
    payload = {"customer_id": customer, "lines": [{"sku_id": sku["id"], "qty": 2}]}
    quote = await client.post("/api/v1/quotes", json=payload)
    assert quote.status_code == 201, quote.text
    quote_id = quote.json()["id"]
    await archive_fixture(async_db, sku["id"])
    kept = await client.patch(f"/api/v1/quotes/{quote_id}", json={"lines": payload["lines"]})
    assert kept.status_code == 200, kept.text
    increase = await client.patch(
        f"/api/v1/quotes/{quote_id}", json={"lines": [{"sku_id": sku["id"], "qty": 3}]}
    )
    assert increase.status_code == 400 and "increasing" in increase.text
    copied = await client.post("/api/v1/quotes", json=payload)
    assert copied.status_code == 400
    accepted = await client.post(f"/api/v1/quotes/{quote_id}/accept", json={"hold_stock": False})
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["lines"][0]["qty"] == 2
    picked = await client.post(
        "/api/v1/picks", json={"sales_order_line_id": accepted.json()["lines"][0]["id"]}
    )
    assert picked.status_code == 201, picked.text


async def test_archived_pending_po_keeps_its_existing_line_only(owner_client, async_db):
    client = owner_client
    sku = await _sku(client, "ARC-PO")
    supplier = await _create_supplier(client, "Archived pending vendor")
    payload = {
        "supplier_id": supplier,
        "submit_for_approval": True,
        "lines": [{"sku_id": sku["id"], "qty": 2, "factory_unit_amount": "10"}],
    }
    response = await client.post("/api/v1/purchase-orders", json=payload)
    assert response.status_code == 201, response.text
    po = response.json()
    await archive_fixture(async_db, sku["id"])
    line = {**payload["lines"][0], "id": po["lines"][0]["id"]}
    kept = await client.patch(f"/api/v1/purchase-orders/{po['id']}", json={"lines": [line]})
    assert kept.status_code == 200, kept.text
    increase = await client.patch(
        f"/api/v1/purchase-orders/{po['id']}", json={"lines": [{**line, "qty": 3}]}
    )
    assert increase.status_code == 400 and "Restore SKU" in increase.text
    reassigned = await client.patch(
        f"/api/v1/purchase-orders/{po['id']}", json={"lines": [payload["lines"][0]]}
    )
    assert reassigned.status_code == 400, reassigned.text
    approved = await client.post(f"/api/v1/purchase-orders/{po['id']}/approve")
    assert approved.status_code == 200, approved.text
    in_transit = await client.post(f"/api/v1/purchase-orders/{po['id']}/on-water")
    assert in_transit.status_code == 200, in_transit.text
    assert (await client.get(f"/api/v1/skus/{sku['id']}")).json()["is_archived"] is True


async def test_archived_stock_remains_visible_and_countable(owner_client, async_db):
    client = owner_client
    location = await _location_id_by_name(client, "Kramerville")
    stocked = await _sku(
        client, "ARC-STOCK", opening_location_id=location, opening_qty=2, opening_cost="100"
    )
    empty = await _sku(client, "ARC-EMPTY")
    await archive_fixture(async_db, stocked["id"])
    await archive_fixture(async_db, empty["id"])
    search = await client.get("/api/v1/search", params={"q": "ARC-STOCK"})
    assert search.status_code == 200, search.text
    assert search.json()["skus"] == []
    inventory = (await client.get("/api/v1/inventory")).json()
    item = next(row for row in inventory if row["sku_id"] == stocked["id"])
    assert (
        item["is_archived"] is True
        and item["sellable"] is False
        and Decimal(str(item["on_hand"])) == 2
    )
    bins = (await client.get("/api/v1/stock/by-bin")).json()["items"]
    assert next(row for row in bins if row["sku_id"] == stocked["id"])["is_archived"] is True
    started = await client.post("/api/v1/stocktakes", json={"location_id": location})
    assert started.status_code == 201, started.text
    lines = {row["sku_id"]: row for row in started.json()["lines"]}
    assert stocked["id"] in lines and empty["id"] not in lines
    # A count may discover additional physical units; archive does not cap stock.
    counted = await client.patch(
        f"/api/v1/stocktakes/{started.json()['id']}/lines/{lines[stocked['id']]['id']}",
        json={"counted_qty": "2.5"},
    )
    assert counted.status_code == 200, counted.text
    completed = await client.post(f"/api/v1/stocktakes/{started.json()['id']}/complete")
    assert completed.status_code == 200, completed.text
    assert (await client.get(f"/api/v1/skus/{stocked['id']}")).json()["is_archived"] is True


async def test_cin7_import_preserves_archive_and_archived_kit_recipe(async_db, tmp_path):
    directory = _fixture_dir(tmp_path / "archive-import")
    await run_import(async_db, directory)
    await async_db.commit()
    recipe = await async_db.scalar(select(SkuBomLine).limit(1))
    assert recipe is not None
    parent = await async_db.get(Sku, recipe.parent_sku_id)
    part = await async_db.get(Sku, recipe.component_sku_id)
    parent.is_archived = True
    recipe.qty = Decimal("0.5")
    await async_db.flush()
    _write_csv(
        directory / "AssemblyBOM_fixture.csv",
        ["ProductSKU", "ComponentSKU", "Quantity"],
        [[parent.our_ref, part.our_ref, "2"]],
    )
    await run_import(async_db, directory)
    await async_db.flush()
    await async_db.refresh(parent)
    await async_db.refresh(recipe)
    assert parent.is_archived is True and recipe.qty == Decimal("0.5")


async def test_csv_import_requires_restore_before_editing_archived_sku(owner_client, async_db):
    sku = await _sku(owner_client, "ARC-CSV")
    await archive_fixture(async_db, sku["id"])
    data = f"our_ref,name,category,retail_inc_vat\n{sku['our_ref']},Changed,Lighting,1150\n"
    response = await owner_client.post(
        "/api/v1/imports/preview", files={"inventory": ("inventory.csv", data, "text/csv")}
    )
    assert response.status_code == 200, response.text
    assert not response.json()["ok"]
    assert "Restore SKU" in str(response.json()["errors"])


async def test_prearchive_till_pick_completes_once_for_exact_quantity(owner_client, async_db):
    client = owner_client
    warehouse = await _location_id_by_name(client, "Kramerville")
    showroom = await _location_id_by_name(client, "Bedfordview")
    stock = await _sku(
        client,
        "ARC-PICK-PART",
        opening_location_id=warehouse,
        opening_qty=2,
        opening_cost="100",
        retail_ex_vat="1000",
    )
    product = await _sku(client, "ARC-PICK-KIT", retail_ex_vat="1000")
    recipe = await client.put(
        f"/api/v1/skus/{product['id']}/bom",
        json={"lines": [{"component_sku_id": stock["id"], "qty": 1}]},
    )
    assert recipe.status_code == 200, recipe.text
    picked = await client.post("/api/v1/picks", json={"sku_id": product["id"], "qty": 1})
    assert picked.status_code == 201, picked.text
    pick_id = picked.json()["id"]
    confirmed = await client.post(f"/api/v1/picks/{pick_id}/confirm", json={})
    assert confirmed.status_code == 200, confirmed.text
    await archive_fixture(async_db, product["id"])
    await archive_fixture(async_db, stock["id"])
    sale = {
        "location_id": showroom,
        "tender": "cash",
        "pick_id": pick_id,
        "lines": [{"sku_id": product["id"], "qty": 2}],
    }
    increased = await client.post("/api/v1/till/sales", json=sale)
    assert increased.status_code == 400, increased.text
    sale["lines"][0]["qty"] = 1
    duplicated = await client.post("/api/v1/till/sales", json={**sale, "lines": sale["lines"] * 2})
    assert duplicated.status_code == 400, duplicated.text
    completed = await client.post("/api/v1/till/sales", json=sale)
    assert completed.status_code == 201, completed.text
    repeated = await client.post("/api/v1/till/sales", json=sale)
    assert repeated.status_code == 400, repeated.text
    cancelled = await client.post(f"/api/v1/picks/{pick_id}/cancel")
    assert cancelled.status_code == 409, cancelled.text
    current = (await client.get(f"/api/v1/skus/{product['id']}")).json()
    assert current["is_archived"] is True


async def test_archived_skus_are_absent_from_reorder_and_whole_public_group(owner_client, async_db):
    from app.crud.ops_commerce import OpsCommerceCRUD
    from app.crud.reorder import ReorderCRUD
    from app.models.product_group import ProductGroup, ProductGroupVariant

    products = [
        await _sku(owner_client, "ARC-FEED-" + str(i), retail_ex_vat="1000") for i in range(2)
    ]
    group = ProductGroup(
        title="Archive test group", options={"Colour": ["A", "B"]}, storefront_published=True
    )
    async_db.add(group)
    await async_db.flush()
    for index, item in enumerate(products):
        sku = await async_db.get(Sku, uuid.UUID(item["id"]))
        sku.storefront_published = True
        sku.reorder_min = 10
        async_db.add(
            ProductGroupVariant(
                product_group_id=group.id,
                source_sku_id=sku.id,
                options={"Colour": str(index)},
                option_signature=str(index),
            )
        )
    await async_db.flush()
    assert len(await OpsCommerceCRUD(async_db).published_products()) == 2
    await archive_fixture(async_db, products[0]["id"])
    # Keep a broken legacy publication group out as a whole; no partial variants.
    assert not await OpsCommerceCRUD(async_db).published_products()
    reorders = await ReorderCRUD(async_db).list_below_min()
    assert products[0]["id"] not in {str(row.sku_id) for row in reorders}
    assert products[1]["id"] in {str(row.sku_id) for row in reorders}


async def test_return_after_archive_restocks_without_reactivation(
    owner_client, async_client, async_db
):
    from tests.test_stock_returns import _till_sale, _return_payload
    from tests.test_till import _inventory_on_hand

    sku_id, location_id, invoice_id, sale = await _till_sale(
        async_client, owner_client, "ARC-RETURN"
    )
    await archive_fixture(async_db, sku_id)
    created = await owner_client.post(
        "/api/v1/returns",
        json=_return_payload(invoice_id, location_id, sale["lines"][0]["id"], "restock"),
    )
    assert created.status_code == 201, created.text
    completed = await owner_client.post(f"/api/v1/returns/{created.json()['id']}/complete")
    assert completed.status_code == 200, completed.text
    assert await _inventory_on_hand(owner_client, sku_id, location_id) == 2
    assert (await owner_client.get(f"/api/v1/skus/{sku_id}")).json()["is_archived"] is True
