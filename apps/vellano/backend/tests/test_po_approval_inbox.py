"""PO approval inbox — approve/reject pending purchase orders."""

from __future__ import annotations

from httpx import AsyncClient

from tests.test_purchase_orders import (
    _create_buyer,
    _create_sku,
    _create_supplier,
    _login_as,
    _relogin_owner,
)


async def _create_pending_po(
    owner_client: AsyncClient,
    buyer_client: AsyncClient,
    *,
    threshold: str = "100.00",
    factory_amount: str = "500.00",
) -> str:
    await _relogin_owner(owner_client)
    patch = await owner_client.patch(
        "/api/v1/settings",
        json={"po_approval_threshold_zar": threshold},
    )
    assert patch.status_code == 200
    supplier_id = await _create_supplier(owner_client, "Inbox Supplier")
    sku = await _create_sku(
        owner_client,
        "INBOX-PO",
        "INBOX-PO-BAR",
        "Inbox PO SKU",
        "Inbox",
        "Fabric",
    )
    buyer = await _login_as(buyer_client, "buyer-po@example.com", "buyer-password")
    created = await buyer.post(
        "/api/v1/purchase-orders",
        json={
            "supplier_id": supplier_id,
            "lines": [{"sku_id": sku["id"], "qty": 1, "factory_unit_amount": factory_amount}],
        },
    )
    assert created.status_code == 201
    assert created.json()["status"] == "pending_approval"
    return created.json()["id"]


async def test_owner_approves_pending_po(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    await _create_buyer(async_client, owner_client)
    po_id = await _create_pending_po(owner_client, async_client)

    await _relogin_owner(owner_client)
    approved = await owner_client.post(f"/api/v1/purchase-orders/{po_id}/approve")
    assert approved.status_code == 200
    assert approved.json()["status"] == "open"

    on_water = await owner_client.post(f"/api/v1/purchase-orders/{po_id}/on-water")
    assert on_water.status_code == 200


async def test_owner_rejects_pending_po(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    await _create_buyer(async_client, owner_client)
    po_id = await _create_pending_po(owner_client, async_client)

    await _relogin_owner(owner_client)
    rejected = await owner_client.post(f"/api/v1/purchase-orders/{po_id}/reject")
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"


async def test_cannot_approve_after_reject(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    await _create_buyer(async_client, owner_client)
    po_id = await _create_pending_po(owner_client, async_client)

    await _relogin_owner(owner_client)
    reject = await owner_client.post(f"/api/v1/purchase-orders/{po_id}/reject")
    assert reject.status_code == 200

    approve = await owner_client.post(f"/api/v1/purchase-orders/{po_id}/approve")
    assert approve.status_code == 409


async def test_buyer_cannot_approve_pending_po(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    await _create_buyer(async_client, owner_client)
    po_id = await _create_pending_po(owner_client, async_client)

    buyer = await _login_as(async_client, "buyer-po@example.com", "buyer-password")
    blocked = await buyer.post(f"/api/v1/purchase-orders/{po_id}/approve")
    assert blocked.status_code == 403
