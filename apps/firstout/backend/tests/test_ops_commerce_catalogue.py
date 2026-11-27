"""The versioned catalogue contract is the seam consumed by commerce adapters."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
from httpx import AsyncClient
from httpx import ASGITransport
from sqlalchemy import func, text, update
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.crud.ops_commerce import SHOP_CATEGORIES
from app.database import Base, get_db
from app.main import app
from app.models.catalogue_list import SkuCategory
from app.models.inventory import LocationStock
from app.models.ops_commerce_acknowledgement import OpsCommerceAcknowledgement
from app.models.product_group import ProductGroup, ProductGroupVariant
from app.models.sku import Sku
from app.models.team import Team


@pytest.mark.asyncio
async def test_published_sku_is_scoped_and_does_not_leak_operational_fields(
    owner_client: AsyncClient,
    async_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    company_id = (await async_db.execute(select(Team.id))).scalar_one()
    monkeypatch.setattr(settings, "ops_commerce_company_id", str(company_id), raising=False)
    monkeypatch.setattr(settings, "ops_commerce_token", "test-ops-token", raising=False)
    monkeypatch.setattr(settings, "ops_commerce_allowed_host", "test", raising=False)

    location = await owner_client.get("/api/v1/locations")
    location_id = next(row["id"] for row in location.json() if row["name"] == "Kramerville")
    created = await owner_client.post(
        "/api/v1/skus",
        json={
            "our_ref": "OPS-SOFA-001",
            "our_barcode": "OPS-SOFA-BAR",
            "name": "Arc sofa",
            "design": "Arc",
            "fabric": "Sand linen",
            "opening_location_id": location_id,
            "opening_qty": 2,
            "opening_unit_cost_zar": "3000.00",
        },
    )
    assert created.status_code == 201
    sku_id = created.json()["id"]
    price = await owner_client.patch(f"/api/v1/skus/{sku_id}", json={"retail_inc_vat": "49990.00"})
    assert price.status_code == 200

    route = "/api/v1/ops-commerce/v1/products"
    headers = {
        "Authorization": "Bearer test-ops-token",
        "X-Ops-Company-ID": str(company_id),
    }
    unpublished = await owner_client.get(route, headers=headers)
    assert unpublished.status_code == 200
    assert unpublished.json()["products"] == []

    sku = await async_db.get(Sku, UUID(sku_id))
    assert sku is not None
    sku.storefront_published = True
    await async_db.flush()

    response = await owner_client.get(route, headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["company_id"] == str(company_id)
    assert len(payload["products"]) == 1
    product = payload["products"][0]
    assert product["source_sku_id"] == sku_id
    assert product["sku"] == "OPS-SOFA-001"
    assert product["name"] == "Arc sofa"
    assert product["price_minor_zar"] == 4999000
    assert product["available_quantity"] == 2
    assert product["revision"]
    assert product["revision"].endswith("Z")
    assert product["observed_at"]
    assert UUID(product["source_sku_id"])
    assert set(product) == {
        "source_sku_id",
        "sku",
        "name",
        "price_minor_zar",
        "available_quantity",
        "revision",
        "observed_at",
        "product_group_id",
        "product_title",
        "options",
        "acknowledged_commitment_ids",
        "made_to_order_offer",
    }
    # Off by default the key is absent, not null: older strict storefront contracts reject it.
    monkeypatch.setattr(settings, "ops_commerce_photo_tokens_enabled", True)
    enabled = (await owner_client.get(route, headers=headers)).json()["products"][0]
    assert set(enabled) == set(product) | {"photo_token"}
    assert enabled["photo_token"] is None
    assert product["acknowledged_commitment_ids"] == []
    assert product["product_group_id"] is None
    assert product["product_title"] is None
    assert product["options"] == {}
    assert product["made_to_order_offer"] is None

    # A finite lead-time offer is operator-controlled and does not change physical stock.
    offer_expiry = (datetime.now(timezone.utc) + timedelta(days=45)).isoformat()
    configured_offer = await owner_client.patch(
        f"/api/v1/skus/{sku_id}",
        json={
            "made_to_order_capacity": 3,
            "made_to_order_lead_time_min_days": 28,
            "made_to_order_lead_time_max_days": 42,
            "made_to_order_expires_at": offer_expiry,
        },
    )
    assert configured_offer.status_code == 200
    first_offer_id = configured_offer.json()["made_to_order_offer_id"]
    assert first_offer_id
    configured_feed = await owner_client.get(route, headers=headers)
    assert configured_feed.status_code == 200
    made_to_order = configured_feed.json()["products"][0]["made_to_order_offer"]
    assert made_to_order == {
        "id": first_offer_id,
        "capacity": 3,
        "min_lead_time_days": 28,
        "max_lead_time_days": 42,
        "expires_at": configured_offer.json()["made_to_order_expires_at"],
    }
    assert configured_feed.json()["products"][0]["available_quantity"] == 2
    range_edit = await owner_client.patch(
        f"/api/v1/skus/{sku_id}",
        json={
            "made_to_order_lead_time_min_days": 30,
            "made_to_order_lead_time_max_days": 45,
        },
    )
    assert range_edit.status_code == 200
    assert range_edit.json()["made_to_order_offer_id"] == first_offer_id
    new_allocation = await owner_client.patch(
        f"/api/v1/skus/{sku_id}", json={"made_to_order_capacity": 4}
    )
    assert new_allocation.status_code == 200
    assert new_allocation.json()["made_to_order_offer_id"] != first_offer_id
    invalid_range = await owner_client.patch(
        f"/api/v1/skus/{sku_id}",
        json={"made_to_order_lead_time_min_days": 50, "made_to_order_lead_time_max_days": 40},
    )
    assert invalid_range.status_code == 400
    expired_offer = await owner_client.patch(
        f"/api/v1/skus/{sku_id}",
        json={
            "made_to_order_expires_at": (
                datetime.now(timezone.utc) - timedelta(seconds=1)
            ).isoformat()
        },
    )
    assert expired_offer.status_code == 400
    disabled_offer = await owner_client.patch(
        f"/api/v1/skus/{sku_id}",
        json={
            "made_to_order_capacity": None,
            "made_to_order_lead_time_min_days": None,
            "made_to_order_lead_time_max_days": None,
            "made_to_order_expires_at": None,
        },
    )
    assert disabled_offer.status_code == 200
    disabled_feed = await owner_client.get(route, headers=headers)
    assert disabled_feed.json()["products"][0]["made_to_order_offer"] is None

    no_machine_auth = await owner_client.get(route)
    assert no_machine_auth.status_code == 401
    wrong_token = await owner_client.get(
        route, headers={**headers, "Authorization": "Bearer other-token"}
    )
    assert wrong_token.status_code == 401
    wrong_company = await owner_client.get(
        route, headers={**headers, "X-Ops-Company-ID": str(UUID(int=1))}
    )
    assert wrong_company.status_code == 403
    wrong_host = await owner_client.get(
        route, headers={**headers, "Host": "other-instance.example"}
    )
    assert wrong_host.status_code == 403
    monkeypatch.setattr(settings, "ops_commerce_allowed_host", "")
    unbound = await owner_client.get(route, headers=headers)
    assert unbound.status_code == 503
    monkeypatch.setattr(settings, "ops_commerce_allowed_host", "test")

    revised_price = await owner_client.patch(
        f"/api/v1/skus/{sku_id}", json={"retail_inc_vat": "12000.00"}
    )
    assert revised_price.status_code == 200
    newer = await owner_client.get(route, headers=headers)
    assert newer.status_code == 200
    assert newer.json()["products"][0]["price_minor_zar"] == 1200000
    assert newer.json()["products"][0]["revision"] > product["revision"]

    # A future importer writes the stock movement and acknowledgement atomically.
    # The snapshot reports the resulting physical stock without subtracting it again.
    acknowledged_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=1)
    await async_db.execute(
        update(LocationStock)
        .where(LocationStock.sku_id == UUID(sku_id))
        .values(on_hand=1, updated_at=acknowledged_at)
    )
    async_db.add(
        OpsCommerceAcknowledgement(
            commitment_id="channel:order-1:line-1",
            source_sku_id=UUID(sku_id),
            quantity=1,
            updated_at=acknowledged_at,
        )
    )
    await async_db.flush()
    after_ack = await owner_client.get(route, headers=headers)
    assert after_ack.status_code == 200
    acknowledged = after_ack.json()["products"][0]
    assert acknowledged["available_quantity"] == 1
    assert acknowledged["acknowledged_commitment_ids"] == ["channel:order-1:line-1"]
    assert acknowledged["revision"] > newer.json()["products"][0]["revision"]


# 1x1 PNG; the upload route resizes it to the stored JPEG.
TINY_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


@pytest.mark.asyncio
async def test_machine_photo_route_serves_only_published_photos_and_token_tracks_the_photo(
    owner_client: AsyncClient,
    async_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    company_id = (await async_db.execute(select(Team.id))).scalar_one()
    monkeypatch.setattr(settings, "ops_commerce_company_id", str(company_id), raising=False)
    monkeypatch.setattr(settings, "ops_commerce_token", "test-ops-token", raising=False)
    monkeypatch.setattr(settings, "ops_commerce_allowed_host", "test", raising=False)
    monkeypatch.setattr(settings, "ops_commerce_photo_tokens_enabled", True)
    headers = {"Authorization": "Bearer test-ops-token", "X-Ops-Company-ID": str(company_id)}

    created = await owner_client.post(
        "/api/v1/skus",
        json={
            "our_ref": "OPS-PHOTO-001",
            "our_barcode": "OPS-PHOTO-BAR",
            "name": "Arc sofa",
            "design": "Arc",
            "fabric": "Sand linen",
        },
    )
    assert created.status_code == 201
    sku_id = created.json()["id"]
    assert (
        await owner_client.patch(f"/api/v1/skus/{sku_id}", json={"retail_inc_vat": "11500.00"})
    ).status_code == 200
    photo_route = f"/api/v1/ops-commerce/v1/products/{sku_id}/photo"
    feed_route = "/api/v1/ops-commerce/v1/products"

    # Unpublished with no photo, then unpublished with a photo: both are not found.
    assert (await owner_client.get(photo_route, headers=headers)).status_code == 404
    uploaded = await owner_client.post(
        f"/api/v1/skus/{sku_id}/photo", files={"photo": ("sku.png", TINY_PNG, "image/png")}
    )
    assert uploaded.status_code == 200
    assert (await owner_client.get(photo_route, headers=headers)).status_code == 404

    sku = await async_db.get(Sku, UUID(sku_id))
    assert sku is not None
    sku.storefront_published = True
    await async_db.flush()

    served = await owner_client.get(photo_route, headers=headers)
    assert served.status_code == 200
    assert served.headers["content-type"] == "image/jpeg"
    assert served.headers["cache-control"] == "no-store"
    assert served.content[:3] == b"\xff\xd8\xff"
    staff_copy = await owner_client.get(f"/api/v1/skus/{sku_id}/photo")
    assert served.content == staff_copy.content

    assert (await owner_client.get(photo_route)).status_code == 401
    assert (
        await owner_client.get(photo_route, headers={**headers, "Authorization": "Bearer other"})
    ).status_code == 401
    assert (
        await owner_client.get(
            photo_route, headers={**headers, "X-Ops-Company-ID": str(UUID(int=1))}
        )
    ).status_code == 403
    assert (
        await owner_client.get(photo_route, headers={**headers, "Host": "other-instance.example"})
    ).status_code == 403
    unknown = f"/api/v1/ops-commerce/v1/products/{UUID(int=7)}/photo"
    assert (await owner_client.get(unknown, headers=headers)).status_code == 404

    first = (await owner_client.get(feed_route, headers=headers)).json()["products"][0]
    assert first["photo_token"] and len(first["photo_token"]) == 64
    # A price edit moves the revision but not the photo token.
    assert (
        await owner_client.patch(f"/api/v1/skus/{sku_id}", json={"retail_inc_vat": "12000.00"})
    ).status_code == 200
    second = (await owner_client.get(feed_route, headers=headers)).json()["products"][0]
    assert second["revision"] > first["revision"]
    assert second["photo_token"] == first["photo_token"]

    # A photo stored under another key is a different photo.
    sku.photo_storage_key = sku.photo_storage_key + ".v2"
    await async_db.flush()
    third = (await owner_client.get(feed_route, headers=headers)).json()["products"][0]
    assert third["photo_token"] not in (None, first["photo_token"])

    sku.storefront_published = False
    await async_db.flush()
    assert (await owner_client.get(photo_route, headers=headers)).status_code == 404


@pytest.mark.asyncio
async def test_service_credential_cannot_select_another_database_backed_instance(
    second_postgres_url: str,
    async_client: AsyncClient,
    async_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_company = (await async_db.execute(select(Team.id))).scalar_one()
    second_engine = create_async_engine(second_postgres_url)
    async with second_engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS citext"))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        await conn.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(second_engine, expire_on_commit=False)() as session:
        other_company = Team(name="Other operational instance")
        session.add(other_company)
        await session.commit()

    async def second_get_db():
        async with async_sessionmaker(second_engine, expire_on_commit=False)() as session:
            yield session

    app.dependency_overrides[get_db] = second_get_db
    monkeypatch.setattr(settings, "ops_commerce_company_id", str(other_company.id))
    monkeypatch.setattr(settings, "ops_commerce_token", "second-instance-token")
    monkeypatch.setattr(settings, "ops_commerce_allowed_host", "other-instance.test")
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://other-instance.test"
    ) as second_client:
        route = "/api/v1/ops-commerce/v1/products"
        first_token = await second_client.get(
            route,
            headers={
                "Authorization": "Bearer first-instance-token",
                "X-Ops-Company-ID": str(first_company),
            },
        )
        assert first_token.status_code == 401
        wrong_company = await second_client.get(
            route,
            headers={
                "Authorization": "Bearer second-instance-token",
                "X-Ops-Company-ID": str(first_company),
            },
        )
        assert wrong_company.status_code == 403
        correct = await second_client.get(
            route,
            headers={
                "Authorization": "Bearer second-instance-token",
                "X-Ops-Company-ID": str(other_company.id),
            },
        )
        assert correct.status_code == 200
        assert correct.json() == {"company_id": str(other_company.id), "products": []}

    app.dependency_overrides.clear()
    await second_engine.dispose()


async def backfill_categories(db: AsyncSession) -> dict[str, SkuCategory]:
    """What migration 120 does for SKUs that only carry a category name: one top-level
    category per lower(trim(name)), its shop section from SHOP_CATEGORIES. Returns them by key.
    """
    keys = (
        await db.execute(
            text("""SELECT DISTINCT lower(btrim(category)) FROM skus
            WHERE category_id IS NULL AND btrim(coalesce(category, '')) <> ''""")
        )
    ).scalars()
    categories = {}
    for key in keys:
        category = await db.scalar(
            select(SkuCategory).where(
                func.lower(SkuCategory.name) == key, SkuCategory.parent_id.is_(None)
            )
        )
        if category is None:
            category = SkuCategory(name=key, shop_category=SHOP_CATEGORIES.get(key))
            db.add(category)
            await db.flush()
        await db.execute(
            update(Sku)
            .where(func.lower(func.trim(Sku.category)) == key, Sku.category_id.is_(None))
            .values(category_id=category.id)
            .execution_options(synchronize_session="fetch")
        )
        categories[key] = category
    await db.flush()
    return categories


@pytest.mark.asyncio
async def test_auto_publish_feeds_photographed_unhidden_shop_category_skus(
    async_client: AsyncClient,
    async_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    company_id = (await async_db.execute(select(Team.id))).scalar_one()
    monkeypatch.setattr(settings, "ops_commerce_company_id", str(company_id))
    monkeypatch.setattr(settings, "ops_commerce_token", "test-ops-token")
    monkeypatch.setattr(settings, "ops_commerce_allowed_host", "test")
    headers = {"Authorization": "Bearer test-ops-token", "X-Ops-Company-ID": str(company_id)}

    def sku(ref: str, category: str | None, photo: bool, **fields: object) -> Sku:
        return Sku(
            our_ref=ref,
            our_barcode=ref,
            name=f"{ref} name",
            design=ref,
            fabric="plain",
            retail_ex_vat=1000,
            category=category,
            photo_storage_key=f"photos/{ref}.jpg" if photo else None,
            **fields,
        )

    skus = {
        "AP-SOFA": sku("AP-SOFA", "  sofas ", True),
        # Published by hand today but has no photo: drops off when the setting turns on.
        "AP-OLD": sku("AP-OLD", "Bedroom", False, storefront_published=True),
        "AP-HIDDEN": sku("AP-HIDDEN", "Dining Room", True, storefront_hidden=True),
        "AP-RUG": sku("AP-RUG", "Rugs", True),
        # Non-ASCII: SQL alone decides the category, so the row maps or drops, never null.
        "AP-TR": sku("AP-TR", "DİNİNG ROOM", True),
        # The rule is per SKU: only G-1 and G-2 qualify. They map to different shop
        # categories, so the first SKU code names the group's category.
        "AP-G-1": sku("AP-G-1", "Coffee and Lamp Tables", True),
        "AP-G-2": sku("AP-G-2", "Bedroom", True),
        "AP-G-3": sku("AP-G-3", "Consoles and TV Units", False),
        "AP-G-4": sku("AP-G-4", "Bedroom", True, storefront_hidden=True),
        "AP-G-5": sku("AP-G-5", "Rugs", True),
        # A group with no qualifying member stays off the shop.
        "AP-H-1": sku("AP-H-1", "Bedroom", False),
        "AP-H-2": sku("AP-H-2", "Rugs", True),
    }
    async_db.add_all(skus.values())
    await async_db.flush()
    # The shop section now comes from the category row (migration 120 backfills it).
    await backfill_categories(async_db)
    shown = ProductGroup(title="Side table", options={"Finish": ["1", "2", "3", "4", "5"]})
    unshown = ProductGroup(title="Bed", options={"Finish": ["1", "2"]})
    async_db.add_all([shown, unshown])
    await async_db.flush()
    for group, refs in (
        (shown, ["AP-G-1", "AP-G-2", "AP-G-3", "AP-G-4", "AP-G-5"]),
        (unshown, ["AP-H-1", "AP-H-2"]),
    ):
        for index, ref in enumerate(refs, start=1):
            async_db.add(
                ProductGroupVariant(
                    product_group_id=group.id,
                    source_sku_id=skus[ref].id,
                    options={"Finish": str(index)},
                    option_signature=f'{{"Finish":"{index}"}}',
                )
            )
    await async_db.flush()
    route = "/api/v1/ops-commerce/v1/products"

    # Off: today's feed, selected by storefront_published, with no new keys.
    off = (await async_client.get(route, headers=headers)).json()["products"]
    assert [row["sku"] for row in off] == ["AP-OLD"]
    assert "shop_category" not in off[0] and "photo_token" not in off[0]

    monkeypatch.setattr(settings, "ops_commerce_auto_publish_enabled", True)
    on = (await async_client.get(route, headers=headers)).json()["products"]
    categories = {row["sku"]: row["shop_category"] for row in on}
    # How the database lowercases İ depends on its collation; either way it is never null.
    assert categories.pop("AP-TR", "dining-room") == "dining-room"
    assert categories == {
        "AP-G-1": "coffee-console-tables",
        "AP-G-2": "coffee-console-tables",
        "AP-SOFA": "sofas-armchairs",
    }
    # Auto-publish sends photo tokens even with the photo-token setting off.
    assert all(len(row["photo_token"]) == 64 for row in on)

    skus["AP-SOFA"].storefront_hidden = True
    await async_db.flush()
    hidden = (await async_client.get(route, headers=headers)).json()["products"]
    assert "AP-SOFA" not in {row["sku"] for row in hidden}


async def _feed(
    client: AsyncClient,
    db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    query: str = "",
) -> dict[str, dict]:
    company_id = (await db.execute(select(Team.id))).scalar_one()
    monkeypatch.setattr(settings, "ops_commerce_company_id", str(company_id))
    monkeypatch.setattr(settings, "ops_commerce_token", "test-ops-token")
    monkeypatch.setattr(settings, "ops_commerce_allowed_host", "test")
    headers = {"Authorization": "Bearer test-ops-token", "X-Ops-Company-ID": str(company_id)}
    response = await client.get(f"/api/v1/ops-commerce/v1/products{query}", headers=headers)
    assert response.status_code == 200, response.text
    return {row["sku"]: row for row in response.json()["products"]}


def _shop_sku(ref: str, category: str | None, **fields: object) -> Sku:
    return Sku(
        our_ref=ref,
        our_barcode=ref,
        name=f"{ref} name",
        design=ref,
        fabric="plain",
        retail_ex_vat=1000,
        category=category,
        photo_storage_key=f"photos/{ref}.jpg",
        **fields,
    )


@pytest.mark.asyncio
async def test_feed_sends_sell_rules_only_when_requested(
    async_client: AsyncClient,
    async_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async_db.add_all(
        [
            _shop_sku("SR-PAIR", None, storefront_published=True, sell_multiple=2, min_sell_qty=4),
            _shop_sku("SR-ONE", None, storefront_published=True),
        ]
    )
    await async_db.flush()

    # Absent by default: an older strict commerce contract rejects unknown keys.
    plain = await _feed(async_client, async_db, monkeypatch)
    assert "sell_multiple" not in plain["SR-PAIR"] and "min_quantity" not in plain["SR-PAIR"]
    ruled = await _feed(async_client, async_db, monkeypatch, "?include_sell_rules=true")
    assert (ruled["SR-PAIR"]["sell_multiple"], ruled["SR-PAIR"]["min_quantity"]) == (2, 4)
    assert (ruled["SR-ONE"]["sell_multiple"], ruled["SR-ONE"]["min_quantity"]) == (1, 1)
    # Independent of the other opt-ins.
    assert "swatch_hex" not in ruled["SR-PAIR"]


@pytest.mark.asyncio
async def test_shop_section_follows_the_category_row_through_a_rename(
    async_client: AsyncClient,
    async_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ops_commerce_auto_publish_enabled", True)
    async_db.add_all(
        [
            _shop_sku("SS-SOFA", "Sofas"),
            _shop_sku("SS-RUG", "Rugs"),
            _shop_sku("SS-NONE", None),
        ]
    )
    await async_db.flush()
    categories = await backfill_categories(async_db)
    before = await _feed(async_client, async_db, monkeypatch)
    assert before["SS-SOFA"]["shop_category"] == "sofas-armchairs"
    # A category with no shop section, and a SKU with no category, stay off the shop
    # exactly as an unmapped name did.
    assert "SS-RUG" not in before and "SS-NONE" not in before

    # Renaming the category (the service cascades the name to skus.category) keeps the section.
    sofas = categories["sofas"]
    sofas.name = "Lounge seating"
    await async_db.execute(
        update(Sku).where(Sku.category_id == sofas.id).values(category="Lounge seating")
    )
    await async_db.flush()
    after = await _feed(async_client, async_db, monkeypatch)
    assert after["SS-SOFA"]["shop_category"] == "sofas-armchairs"

    # Giving the rug category a section puts its SKUs on the shop; clearing it takes them off.
    categories["rugs"].shop_category = "bedroom"
    await async_db.flush()
    assert (await _feed(async_client, async_db, monkeypatch))["SS-RUG"]["shop_category"] == (
        "bedroom"
    )
    sofas.shop_category = None
    await async_db.flush()
    assert "SS-SOFA" not in await _feed(async_client, async_db, monkeypatch)
