"""Group existing SKUs through the operator API and project them for commerce."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.team import Team


async def _sku(client: AsyncClient, suffix: str) -> str:
    created = await client.post(
        "/api/v1/skus",
        json={
            "our_ref": f"GROUP-{suffix}",
            "our_barcode": f"GROUP-BAR-{suffix}",
            "name": f"Arc sofa {suffix}",
            "design": f"Group Arc {suffix}",
            "fabric": f"Group fabric {suffix}",
        },
    )
    assert created.status_code == 201, created.text
    return created.json()["id"]


@pytest.mark.asyncio
async def test_group_variants_and_projection_keep_sku_identity(
    owner_client: AsyncClient,
    async_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    company_id = (await async_db.execute(select(Team.id))).scalar_one()
    monkeypatch.setattr(settings, "ops_commerce_company_id", str(company_id))
    monkeypatch.setattr(settings, "ops_commerce_token", "test-ops-token")
    monkeypatch.setattr(settings, "ops_commerce_allowed_host", "test")
    headers = {"Authorization": "Bearer test-ops-token", "X-Ops-Company-ID": str(company_id)}

    sand = await _sku(owner_client, "SAND")
    charcoal = await _sku(owner_client, "CHARCOAL")
    for sku_id in (sand, charcoal):
        response = await owner_client.patch(
            f"/api/v1/skus/{sku_id}",
            json={"retail_inc_vat": "11500.00", "storefront_published": True},
        )
        assert response.status_code == 200, response.text

    body = {
        "title": "Arc sofa",
        "options": {"Colour": ["Sand", "Charcoal"]},
        "variants": [
            {"source_sku_id": sand, "options": {"Colour": "Sand"}},
            {"source_sku_id": charcoal, "options": {"Colour": "Charcoal"}},
        ],
    }
    created = await owner_client.post("/api/v1/product-groups", json=body)
    assert created.status_code == 201, created.text
    group_id = created.json()["id"]
    assert created.json()["storefront_published"] is False
    assert {row["sku"] for row in created.json()["variants"]} == {"GROUP-SAND", "GROUP-CHARCOAL"}

    route = "/api/v1/ops-commerce/v1/products"
    before = await owner_client.get(route, headers=headers)
    assert before.status_code == 200
    assert all(row["source_sku_id"] not in (sand, charcoal) for row in before.json()["products"])

    published = await owner_client.patch(
        f"/api/v1/product-groups/{group_id}", json={"storefront_published": True}
    )
    assert published.status_code == 200, published.text
    projected = await owner_client.get(route, headers=headers)
    rows = [row for row in projected.json()["products"] if row["source_sku_id"] in (sand, charcoal)]
    assert {row["source_sku_id"] for row in rows} == {sand, charcoal}
    assert {row["options"]["Colour"] for row in rows} == {"Sand", "Charcoal"}
    assert all(row["product_group_id"] == group_id for row in rows)
    assert all(row["product_title"] == "Arc sofa" for row in rows)
    assert all(row["price_minor_zar"] == 1150000 for row in rows)
    assert all("photo_storage_key" not in row and "supplier_ref" not in row for row in rows)

    before_remap = next(row["revision"] for row in rows if row["source_sku_id"] == sand)
    remapped = await owner_client.put(
        f"/api/v1/product-groups/{group_id}/variants",
        json={
            "variants": [
                {"source_sku_id": sand, "options": {"Colour": "Charcoal"}},
                {"source_sku_id": charcoal, "options": {"Colour": "Sand"}},
            ]
        },
    )
    assert remapped.status_code == 200, remapped.text
    remap_feed = await owner_client.get(route, headers=headers)
    remap_sand = next(row for row in remap_feed.json()["products"] if row["source_sku_id"] == sand)
    assert remap_sand["options"] == {"Colour": "Charcoal"}
    assert remap_sand["revision"] > before_remap

    previous_revision = remap_sand["revision"]
    revised = await owner_client.patch(f"/api/v1/skus/{sand}", json={"retail_inc_vat": "12000.00"})
    assert revised.status_code == 200
    after = await owner_client.get(route, headers=headers)
    sand_row = next(row for row in after.json()["products"] if row["source_sku_id"] == sand)
    assert sand_row["price_minor_zar"] == 1200000
    assert sand_row["revision"] > previous_revision
    assert sand_row["product_group_id"] == group_id

    unpublished = await owner_client.patch(
        f"/api/v1/skus/{charcoal}", json={"storefront_published": False}
    )
    assert unpublished.status_code == 200
    withheld = await owner_client.get(route, headers=headers)
    assert all(row["product_group_id"] != group_id for row in withheld.json()["products"])


@pytest.mark.asyncio
async def test_group_rejects_ambiguous_or_missing_selections_and_republication(
    owner_client: AsyncClient,
) -> None:
    first = await _sku(owner_client, "BAD-ONE")
    second = await _sku(owner_client, "BAD-TWO")
    case_duplicate = await owner_client.post(
        "/api/v1/product-groups",
        json={"title": "Duplicate option names", "options": {"Colour": ["Sand"], "colour": ["Charcoal"]}},
    )
    assert case_duplicate.status_code == 409
    base = {
        "title": "Bad choices",
        "options": {"Colour": ["Sand", "Charcoal"]},
    }
    missing = await owner_client.post(
        "/api/v1/product-groups",
        json={**base, "variants": [{"source_sku_id": first, "options": {}}]},
    )
    assert missing.status_code == 400
    ambiguous = await owner_client.post(
        "/api/v1/product-groups",
        json={
            **base,
            "variants": [
                {"source_sku_id": first, "options": {"Colour": "Sand"}},
                {"source_sku_id": second, "options": {"Colour": "Sand"}},
            ],
        },
    )
    assert ambiguous.status_code == 409
    created = await owner_client.post(
        "/api/v1/product-groups",
        json={
            **base,
            "variants": [{"source_sku_id": first, "options": {"Colour": "Sand"}}],
        },
    )
    assert created.status_code == 201
    group_id = created.json()["id"]
    premature = await owner_client.patch(
        f"/api/v1/product-groups/{group_id}", json={"storefront_published": True}
    )
    assert premature.status_code == 400
    duplicate = await owner_client.post(
        "/api/v1/product-groups",
        json={
            **base,
            "variants": [{"source_sku_id": first, "options": {"Colour": "Charcoal"}}],
        },
    )
    assert duplicate.status_code == 409
    not_found = await owner_client.put(
        f"/api/v1/product-groups/{group_id}/variants",
        json={"variants": [{"source_sku_id": str(uuid.uuid4()), "options": {"Colour": "Sand"}}]},
    )
    assert not_found.status_code == 404
