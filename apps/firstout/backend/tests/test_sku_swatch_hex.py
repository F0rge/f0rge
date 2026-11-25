"""SKU finish colour: validated on the catalogue API and offered to the shop feed on request."""

from __future__ import annotations

from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.sku import Sku
from app.models.team import Team


async def _create(owner_client: AsyncClient, ref: str, **extra: object) -> dict:
    response = await owner_client.post(
        "/api/v1/skus",
        json={"our_ref": ref, "name": "Arc sofa", "design": ref, "fabric": "Sand linen", **extra},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_swatch_hex_is_normalised_validated_and_cleared(owner_client: AsyncClient) -> None:
    plain = await _create(owner_client, "SWATCH-001")
    assert plain["swatch_hex"] is None

    created = await _create(owner_client, "SWATCH-002", swatch_hex="#9B9592")
    assert created["swatch_hex"] == "#9b9592"
    path = f"/api/v1/skus/{created['id']}"
    assert (await owner_client.get(path)).json()["swatch_hex"] == "#9b9592"

    for invalid in ("9b9592", "#9b959", "#9b95921", "#ggggggg", "#gggggg", "red", 123):
        rejected = await owner_client.patch(path, json={"swatch_hex": invalid})
        assert rejected.status_code == 422, invalid
    bad_create = await owner_client.post(
        "/api/v1/skus",
        json={
            "our_ref": "SWATCH-BAD",
            "name": "x",
            "design": "x",
            "fabric": "x",
            "swatch_hex": "#12",
        },
    )
    assert bad_create.status_code == 422

    changed = await owner_client.patch(path, json={"swatch_hex": " #A1B2C3 "})
    assert changed.status_code == 200
    assert changed.json()["swatch_hex"] == "#a1b2c3"

    # Other edits leave the colour alone.
    renamed = await owner_client.patch(path, json={"name": "Arc sofa, sand"})
    assert renamed.json()["swatch_hex"] == "#a1b2c3"

    blank = await owner_client.patch(path, json={"swatch_hex": ""})
    assert blank.status_code == 200
    assert blank.json()["swatch_hex"] is None

    await owner_client.patch(path, json={"swatch_hex": "#a1b2c3"})
    cleared = await owner_client.patch(path, json={"swatch_hex": None})
    assert cleared.json()["swatch_hex"] is None


async def test_feed_sends_swatch_hex_only_when_requested(
    owner_client: AsyncClient,
    async_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    company_id = (await async_db.execute(select(Team.id))).scalar_one()
    monkeypatch.setattr(settings, "ops_commerce_company_id", str(company_id), raising=False)
    monkeypatch.setattr(settings, "ops_commerce_token", "test-ops-token", raising=False)
    monkeypatch.setattr(settings, "ops_commerce_allowed_host", "test", raising=False)

    sku_id = (await _create(owner_client, "SWATCH-FEED", swatch_hex="#9B9592"))["id"]
    priced = await owner_client.patch(f"/api/v1/skus/{sku_id}", json={"retail_inc_vat": "11500.00"})
    assert priced.status_code == 200
    sku = await async_db.get(Sku, UUID(sku_id))
    assert sku is not None
    sku.storefront_published = True
    await async_db.flush()

    route = "/api/v1/ops-commerce/v1/products"
    headers = {"Authorization": "Bearer test-ops-token", "X-Ops-Company-ID": str(company_id)}

    async def feed_row(query: str = "") -> dict:
        response = await owner_client.get(f"{route}{query}", headers=headers)
        assert response.status_code == 200
        return next(row for row in response.json()["products"] if row["source_sku_id"] == sku_id)

    # Absent by default: an older strict commerce contract rejects unknown keys.
    assert "swatch_hex" not in await feed_row()
    assert (await feed_row("?include_swatch=true"))["swatch_hex"] == "#9b9592"

    await owner_client.patch(f"/api/v1/skus/{sku_id}", json={"swatch_hex": None})
    assert (await feed_row("?include_swatch=true"))["swatch_hex"] is None
