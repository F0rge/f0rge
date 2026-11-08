"""Clerk-approved trade customer drafts remain subject to staff confirmation."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from urllib.parse import urlsplit

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.tenant_signup import get_clerk_api
from app.main import app
from app.models.membership import Membership
from app.models.user import User
from tests.conftest import independent_request_sessions, signed_clerk_token
from tests.test_purchase_orders import _location_id_by_name, _relogin_owner
from tests.test_till import _inventory_on_hand, _set_retail_price
from tests.test_transfers import _receive_qty_at_location


@pytest.fixture
async def verified_trade_provider():
    # Only the external Clerk profile lookup is replaced; JWT verification,
    # invitation redemption, selector binding and all commerce requests are real.
    provider = SimpleNamespace(
        user=AsyncMock(
            return_value={
                "id": "user_trade_designer",
                "primary_email_address_id": "email_verified",
                "email_addresses": [
                    {
                        "id": "email_verified",
                        "email_address": "designer@studio.example",
                        "verification": {"status": "verified"},
                    }
                ],
            }
        )
    )
    previous = app.dependency_overrides.get(get_clerk_api)
    app.dependency_overrides[get_clerk_api] = lambda: provider
    try:
        yield provider
    finally:
        if previous is None:
            app.dependency_overrides.pop(get_clerk_api, None)
        else:
            app.dependency_overrides[get_clerk_api] = previous


async def test_trade_portal_draft_order_staff_confirm_holds(
    async_client: AsyncClient,
    owner_client: AsyncClient,
    async_db: AsyncSession,
    verified_trade_provider,
) -> None:
    async with independent_request_sessions(async_db):
        data = await _receive_qty_at_location(
            async_client, owner_client, qty=2, location_name="Kramerville", our_ref="PORTAL-SOFA"
        )
        sku_id = data["sku"]["id"]
        await _set_retail_price(owner_client, sku_id, "1000.00")
        location_id = await _location_id_by_name(owner_client, "Kramerville")
        customer = await owner_client.post(
            "/api/v1/customers",
            json={"name": "Trade Studio", "customer_type": "trade", "email": "studio@example.com"},
        )
        assert customer.status_code == 201, customer.text
        customer_id = customer.json()["id"]
        invited = await owner_client.post(
            f"/api/v1/customers/{customer_id}/portal-invitations",
            json={"email": "designer@studio.example"},
        )
        assert invited.status_code == 201, invited.text
        url = urlsplit(invited.json()["invitation_url"])
        assert not url.query and url.fragment.startswith("token=")
        before = (
            await async_db.scalar(select(func.count()).select_from(User)),
            await async_db.scalar(select(func.count()).select_from(Membership)),
        )
        personal = {
            "Authorization": "Bearer " + signed_clerk_token("user_trade_designer", status="active")
        }
        accepted = await async_client.post(
            "/api/v1/portal/invitations/accept",
            headers=personal,
            json={"token": url.fragment.split("=", 1)[1]},
        )
        assert accepted.status_code == 201, accepted.text
        assert not accepted.cookies
        access = accepted.json()
        assert access["customer_id"] == customer_id
        after = (
            await async_db.scalar(select(func.count()).select_from(User)),
            await async_db.scalar(select(func.count()).select_from(Membership)),
        )
        assert after == before
        portal_headers = {**personal, "X-Firstout-Portal-Access": access["id"]}
        async_client.cookies.clear()
        async_client.headers.pop("Authorization", None)
        assert (await async_client.get("/api/v1/quotes")).status_code == 401
        assert (await async_client.get("/api/v1/quotes", headers=portal_headers)).status_code == 401
        me = await async_client.get("/api/v1/portal/me", headers=portal_headers)
        assert me.status_code == 200 and me.json()["customer_id"] == customer_id
        catalogue = await async_client.get("/api/v1/portal/catalogue", headers=portal_headers)
        assert catalogue.status_code == 200
        assert any(item["id"] == sku_id for item in catalogue.json())
        placed = await async_client.post(
            "/api/v1/portal/orders",
            headers=portal_headers,
            json={"lines": [{"sku_id": sku_id, "qty": 1}]},
        )
        assert placed.status_code == 201, placed.text
        draft = placed.json()
        assert draft["status"] == "draft" and draft["hold_stock"] is False
        assert draft["so_number"].startswith("SO-")
        await _relogin_owner(owner_client)
        listed = await owner_client.get("/api/v1/orders")
        assert listed.status_code == 200
        assert any(
            item["id"] == draft["id"] and item["status"] == "draft"
            for item in listed.json()["items"]
        )
        on_hand_before = await _inventory_on_hand(owner_client, sku_id, location_id)
        confirmed = await owner_client.post(
            f"/api/v1/orders/{draft['id']}/confirm",
            json={"location_id": location_id, "hold_stock": True},
        )
        assert confirmed.status_code == 200, confirmed.text
        assert confirmed.json()["status"] == "open" and confirmed.json()["hold_stock"] is True
        assert await _inventory_on_hand(owner_client, sku_id, location_id) == on_hand_before - 1
