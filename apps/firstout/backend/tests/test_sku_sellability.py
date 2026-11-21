"""Source non-sale products remain stocked and readable but cannot start new sales."""

from __future__ import annotations

import datetime
import uuid

import pytest

from app.models.sku import Sku
from app.schemas.sales_order import SalesOrderCreate
from app.services.sales_orders import SalesOrdersService
from f0rge_core.exceptions import ValidationError
from tests.conftest import authenticate_as, create_test_staff
from tests.test_fractional_inventory import fractional_sku, locations
from tests.test_ops_commerce_orders import _paid_order_payload
from tests.test_ops_commerce_orders import ops_headers as ops_headers


async def nonsale_fixture(client):
    sku, location_id = await fractional_sku(
        client, qty="2", location="Bedfordview", suffix="NONSALE"
    )
    patched = await client.patch(
        f"/api/v1/skus/{sku['id']}", json={"retail_inc_vat": "115", "is_sellable": False}
    )
    assert patched.status_code == 200 and patched.json()["is_sellable"] is False
    customer = await client.post("/api/v1/customers", json={"name": "Non-sale customer"})
    assert customer.status_code == 201
    return sku, location_id, customer.json()["id"]


async def test_sellability_create_patch_read_and_permissions(owner_client):
    sku = await owner_client.post(
        "/api/v1/skus",
        json={
            "our_ref": "CREATE-NONSALE",
            "name": "Create non-sale",
            "design": "Create non-sale",
            "fabric": "Material",
            "is_sellable": False,
        },
    )
    assert sku.status_code == 201 and sku.json()["is_sellable"] is False
    sku_id = sku.json()["id"]
    assert (await owner_client.get(f"/api/v1/skus/{sku_id}")).json()["is_sellable"] is False
    assert (
        await owner_client.patch(f"/api/v1/skus/{sku_id}", json={"is_sellable": None})
    ).status_code == 400
    await create_test_staff(owner_client, email="sellable-warehouse@example.com", role="warehouse")
    assert (
        await authenticate_as(owner_client, "sellable-warehouse@example.com")
    ).status_code == 200
    assert (
        await owner_client.patch(f"/api/v1/skus/{sku_id}", json={"is_sellable": True})
    ).status_code == 403
    assert (await owner_client.get(f"/api/v1/skus/{sku_id}")).json()["is_sellable"] is False


@pytest.mark.parametrize(
    "document", ["quotes", "invoices", "till/sales", "laybys", "orders-service"]
)
async def test_nonsale_sku_rejected_by_new_sales_even_with_valid_price(
    owner_client, async_db, document
):
    sku, location_id, customer_id = await nonsale_fixture(owner_client)
    payload = {"customer_id": customer_id, "lines": [{"sku_id": sku["id"], "qty": 1}]}
    if document == "orders-service":
        with pytest.raises(ValidationError, match="not available for new sales"):
            await SalesOrdersService(async_db).create_draft(
                SalesOrderCreate.model_validate(payload)
            )
        return
    if document == "invoices":
        payload.update(issue_date=datetime.date.today().isoformat())
        payload["lines"][0].update(description="Non-sale product")
    if document in ("till/sales", "laybys"):
        payload.update(location_id=location_id, tender="cash")
    if document == "laybys":
        payload.update(
            due_date=datetime.date.today().isoformat(), hold_stock=False, deposit_amount="10"
        )
    response = await owner_client.post(f"/api/v1/{document}", json=payload)
    assert response.status_code == 400, response.text
    assert "not available for new sales" in response.text


async def test_nonsale_stock_and_purchasing_remain_accessible(owner_client):
    sku, _location_id, _customer = await nonsale_fixture(owner_client)
    inventory = await owner_client.get("/api/v1/inventory")
    assert inventory.status_code == 200
    assert next(row for row in inventory.json() if row["sku_id"] == sku["id"])["on_hand"] == 2
    supplier = await owner_client.post(
        "/api/v1/suppliers", json={"name": "Non-sale component supplier"}
    )
    po = await owner_client.post(
        "/api/v1/purchase-orders",
        json={
            "supplier_id": supplier.json()["id"],
            "lines": [{"sku_id": sku["id"], "qty": 1, "factory_unit_amount": "100"}],
        },
    )
    assert po.status_code == 201, po.text
    restored = await owner_client.patch(f"/api/v1/skus/{sku['id']}", json={"is_sellable": True})
    assert restored.status_code == 200
    customer = await owner_client.post("/api/v1/customers", json={"name": "Restored sale customer"})
    quote = await owner_client.post(
        "/api/v1/quotes",
        json={"customer_id": customer.json()["id"], "lines": [{"sku_id": sku["id"], "qty": 1}]},
    )
    assert quote.status_code == 201


async def test_existing_quote_continues_after_sku_becomes_nonsale(owner_client):
    sku, location_id = await fractional_sku(owner_client, qty="2")
    await owner_client.patch(f"/api/v1/skus/{sku['id']}", json={"retail_inc_vat": "115"})
    customer = await owner_client.post(
        "/api/v1/customers", json={"name": "Existing quote customer"}
    )
    quote = await owner_client.post(
        "/api/v1/quotes",
        json={"customer_id": customer.json()["id"], "lines": [{"sku_id": sku["id"], "qty": 1}]},
    )
    assert quote.status_code == 201
    await owner_client.patch(f"/api/v1/skus/{sku['id']}", json={"is_sellable": False})
    accepted = await owner_client.post(
        f"/api/v1/quotes/{quote.json()['id']}/accept",
        json={"hold_stock": True, "location_id": location_id},
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["lines"][0]["held_qty"] == 1
    assert (await owner_client.get(f"/api/v1/quotes/{quote.json()['id']}/pdf")).status_code == 200


async def test_paid_storefront_handoff_preserves_existing_nonsale_commitment(
    owner_client,
    ops_headers,  # noqa: F811 — imported pytest fixture
):
    payload, sku_id = await _paid_order_payload(owner_client, fixture_tag="nonsale")
    payload["company_id"] = ops_headers["X-Ops-Company-ID"]
    await owner_client.patch(f"/api/v1/skus/{sku_id}", json={"is_sellable": False})
    result = await owner_client.post(
        "/api/v1/ops-commerce/v1/orders", json=payload, headers=ops_headers
    )
    assert result.status_code == 201, result.text
    assert (await owner_client.get(f"/api/v1/skus/{sku_id}")).json()["is_sellable"] is False


async def test_shop_feed_excludes_nonsale_and_does_not_sum_split_fractions(
    owner_client,
    async_db,
    ops_headers,  # noqa: F811 — imported pytest fixture
):
    from app.crud.ops_commerce import OpsCommerceCRUD

    sku, location_id = await fractional_sku(owner_client, qty="0.5")
    await owner_client.patch(f"/api/v1/skus/{sku['id']}", json={"retail_inc_vat": "115"})
    model = await async_db.get(Sku, uuid.UUID(sku["id"]))
    model.storefront_published = True
    from app.models.inventory import LocationStock

    async_db.add(
        LocationStock(
            sku_id=model.id,
            location_id=uuid.UUID((await locations(owner_client))["Bedfordview"]),
            on_hand="0.5",
        )
    )
    await async_db.flush()
    feed = await OpsCommerceCRUD(async_db).published_products()
    assert next(row for row in feed if row.id == model.id).available_quantity == 0
    model.is_sellable = False
    await async_db.flush()
    assert model.id not in {row.id for row in await OpsCommerceCRUD(async_db).published_products()}
