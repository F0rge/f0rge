"""Ops availability includes operational holds before commerce reads it."""

from __future__ import annotations

import re

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.team import Team
from tests.test_sales_orders import _open_held_order


@pytest.mark.asyncio
async def test_held_stock_is_counted_once_in_versioned_ops_snapshot(
    async_client: AsyncClient,
    owner_client: AsyncClient,
    async_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    company_id = (await async_db.execute(select(Team.id))).scalar_one()
    monkeypatch.setattr(settings, "ops_commerce_company_id", str(company_id))
    monkeypatch.setattr(settings, "ops_commerce_token", "qa-ops-token")
    monkeypatch.setattr(settings, "ops_commerce_allowed_host", "test")
    headers = {"Authorization": "Bearer qa-ops-token", "X-Ops-Company-ID": str(company_id)}

    order = await _open_held_order(
        async_client, owner_client, "OPS-HOLD-746", qty=2, hold_qty=1, deposit=None
    )
    sku_id = order["_sku_id"]
    published = await owner_client.patch(
        f"/api/v1/skus/{sku_id}", json={"storefront_published": True}
    )
    assert published.status_code == 200, published.text

    held = await owner_client.get("/api/v1/ops-commerce/v1/products", headers=headers)
    assert held.status_code == 200, held.text
    product = next(row for row in held.json()["products"] if row["source_sku_id"] == sku_id)
    assert product["available_quantity"] == 1
    assert product["acknowledged_commitment_ids"] == []
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{6}Z", product["revision"])

    cancelled = await owner_client.post(f"/api/v1/orders/{order['id']}/cancel")
    assert cancelled.status_code == 200, cancelled.text
    released = await owner_client.get("/api/v1/ops-commerce/v1/products", headers=headers)
    assert released.status_code == 200, released.text
    restored = next(row for row in released.json()["products"] if row["source_sku_id"] == sku_id)
    assert restored["available_quantity"] == 2
    assert restored["acknowledged_commitment_ids"] == []
