"""The versioned catalogue contract is the seam consumed by commerce adapters."""

from __future__ import annotations

from uuid import UUID

import pytest
from httpx import AsyncClient
from httpx import ASGITransport
from sqlalchemy import text
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

from app.config import settings
from app.database import Base, get_db
from app.main import app
from app.models.team import Team
from f0rge_testing import async_url


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
    price = await owner_client.patch(f"/api/v1/skus/{sku_id}", json={"retail_inc_vat": "11500.00"})
    assert price.status_code == 200

    route = "/api/v1/ops-commerce/v1/products"
    headers = {
        "Authorization": "Bearer test-ops-token",
        "X-Ops-Company-ID": str(company_id),
    }
    unpublished = await owner_client.get(route, headers=headers)
    assert unpublished.status_code == 200
    assert unpublished.json()["products"] == []

    published = await owner_client.patch(
        f"/api/v1/skus/{sku_id}", json={"storefront_published": True}
    )
    assert published.status_code == 200
    assert published.json()["storefront_published"] is True
    invalid_flag = await owner_client.patch(
        f"/api/v1/skus/{sku_id}", json={"storefront_published": None}
    )
    assert invalid_flag.status_code == 400

    response = await owner_client.get(route, headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["company_id"] == str(company_id)
    assert len(payload["products"]) == 1
    product = payload["products"][0]
    assert product["source_sku_id"] == sku_id
    assert product["sku"] == "OPS-SOFA-001"
    assert product["name"] == "Arc sofa"
    assert product["price_minor_zar"] == 1150000
    assert product["available_quantity"] == 2
    assert product["revision"]
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
    }

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


@pytest.mark.asyncio
async def test_service_credential_cannot_select_another_database_backed_instance(
    async_client: AsyncClient,
    async_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_company = (await async_db.execute(select(Team.id))).scalar_one()
    with PostgresContainer("postgres:16") as second_postgres:
        second_engine = create_async_engine(async_url(second_postgres))
        async with second_engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS citext"))
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
