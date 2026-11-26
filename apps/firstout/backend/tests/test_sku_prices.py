"""S5 SKU wholesale/retail VAT price tests."""

from __future__ import annotations

from decimal import Decimal

import pytest
from tests.conftest import authenticate_as, create_test_staff

from httpx import AsyncClient


async def _create_sku(owner_client: AsyncClient, suffix: str) -> dict:
    resp = await owner_client.post(
        "/api/v1/skus",
        json={
            "our_ref": f"VEL-PRICE-{suffix}",
            "our_barcode": f"BAR-PRICE-{suffix}",
            "name": f"Price test {suffix}",
            "design": f"Design {suffix}",
            "fabric": f"Fabric {suffix}",
        },
    )
    assert resp.status_code == 201
    return resp.json()


async def test_create_sku_prices_null(owner_client: AsyncClient) -> None:
    body = await _create_sku(owner_client, "NULL")
    assert body["stockist_ex_vat"] is None
    assert body["stockist_inc_vat"] is None
    assert body["wholesale_ex_vat"] is None
    assert body["wholesale_inc_vat"] is None
    assert body["decorator_ex_vat"] is None
    assert body["decorator_inc_vat"] is None
    assert body["retail_ex_vat"] is None
    assert body["retail_inc_vat"] is None


async def test_patch_wholesale_ex_vat_derives_inc(owner_client: AsyncClient) -> None:
    sku = await _create_sku(owner_client, "WEX")
    resp = await owner_client.patch(
        f"/api/v1/skus/{sku['id']}",
        json={"wholesale_ex_vat": "100.00"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["wholesale_ex_vat"] == "100.00"
    assert body["wholesale_inc_vat"] == "115.00"


async def test_patch_retail_inc_vat_derives_ex(owner_client: AsyncClient) -> None:
    sku = await _create_sku(owner_client, "RINC")
    resp = await owner_client.patch(
        f"/api/v1/skus/{sku['id']}",
        json={"retail_inc_vat": "2300.00"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["retail_inc_vat"] == "2300.00"
    assert body["retail_ex_vat"] == "2000.00"


@pytest.mark.parametrize(
    ("vat_rate", "gross", "net", "invoice_total"),
    [
        ("0.15", "999.00", "868.70", "999.01"),
        ("0.16", "3990.00", "3439.66", "3990.01"),
        ("0.1501", "2.95", "2.56", "2.94"),
    ],
)
async def test_exact_catalogue_retail_price_keeps_invoice_rounding(
    owner_client: AsyncClient, vat_rate: str, gross: str, net: str, invoice_total: str
) -> None:
    sku = await _create_sku(owner_client, "EXACT-RETAIL")
    sku_url = f"/api/v1/skus/{sku['id']}"
    settings = await owner_client.patch("/api/v1/settings", json={"vat_rate": vat_rate})
    assert settings.status_code == 200, settings.text

    initial = await owner_client.patch(sku_url, json={"retail_ex_vat": net})
    assert initial.status_code == 200, initial.text
    assert initial.json()["retail_inc_vat"] == invoice_total

    updated = await owner_client.patch(sku_url, json={"retail_inc_vat": gross})
    assert updated.status_code == 200, updated.text
    reloaded = await owner_client.get(sku_url)
    assert reloaded.status_code == 200, reloaded.text
    for response in (updated, reloaded):
        assert response.json()["retail_inc_vat"] == gross
        assert response.json()["retail_ex_vat"] == net

    invoice = await owner_client.post(
        f"{sku_url}/price-preview", json={"classification": "Retail", "quantity": 1}
    )
    assert invoice.status_code == 200, invoice.text
    assert invoice.json()["unit_ex_vat"] == net
    assert invoice.json()["total_inc_vat"] == invoice_total


async def test_exact_retail_price_preview_accepts_the_existing_invoice_limit(
    owner_client: AsyncClient,
) -> None:
    sku = await _create_sku(owner_client, "MAX-RETAIL")
    sku_url = f"/api/v1/skus/{sku['id']}"
    settings = await owner_client.patch("/api/v1/settings", json={"vat_rate": "0.75"})
    assert settings.status_code == 200, settings.text

    prices = {"retail_inc_vat": "17499999999.99"}
    preview = await owner_client.post(
        f"{sku_url}/price-preview",
        json={"classification": "Retail", "quantity": 1, "price_changes": prices},
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["unit_ex_vat"] == "9999999999.99"
    saved = await owner_client.patch(sku_url, json=prices)
    assert saved.status_code == 200, saved.text
    assert saved.json()["retail_inc_vat"] == prices["retail_inc_vat"]


async def test_patch_preserves_rounding_for_legacy_sub_cent_retail_input(
    owner_client: AsyncClient,
) -> None:
    sku = await _create_sku(owner_client, "SUB-CENT-RETAIL")
    updated = await owner_client.patch(
        f"/api/v1/skus/{sku['id']}", json={"retail_inc_vat": "999.004"}
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["retail_inc_vat"] == "999.01"
    assert updated.json()["retail_ex_vat"] == "868.70"


async def test_inc_to_ex_round_half_up(owner_client: AsyncClient) -> None:
    sku = await _create_sku(owner_client, "ROUND")
    resp = await owner_client.patch(
        f"/api/v1/skus/{sku['id']}",
        json={"retail_inc_vat": "2500.00"},
    )
    assert resp.status_code == 200
    assert resp.json()["retail_ex_vat"] == "2173.91"


async def test_catalogue_prices_convert_at_the_team_rate(owner_client: AsyncClient) -> None:
    sku = await _create_sku(owner_client, "VAT15")
    resp = await owner_client.patch(
        f"/api/v1/skus/{sku['id']}",
        json={"wholesale_ex_vat": "100.00"},
    )
    assert resp.status_code == 200
    assert resp.json()["wholesale_inc_vat"] == "115.00"

    # ADR 0003: no hard-coded rate; the catalogue follows the team's setting today.
    settings = await owner_client.patch("/api/v1/settings", json={"vat_rate": "0.16"})
    assert settings.status_code == 200, settings.text
    resp = await owner_client.patch(
        f"/api/v1/skus/{sku['id']}",
        json={"retail_inc_vat": "1160.00"},
    )
    assert resp.status_code == 200
    assert resp.json()["wholesale_inc_vat"] == "116.00"
    assert resp.json()["retail_ex_vat"] == "1000.00"


async def test_unauthenticated_patch_returns_401(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    sku = await _create_sku(owner_client, "UNAUTH")
    async_client.cookies.clear()
    async_client.headers.pop("Authorization", None)
    resp = await async_client.patch(
        f"/api/v1/skus/{sku['id']}",
        json={"wholesale_ex_vat": "100.00"},
    )
    assert resp.status_code == 401


async def test_till_cannot_patch_prices_but_can_get(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    sku = await _create_sku(owner_client, "TILL")
    await create_test_staff(
        owner_client,
        **{
            "email": "till-price@example.com",
            "password": "till-password",
            "role": "till",
        },
    )

    async_client.cookies.clear()
    async_client.headers.pop("Authorization", None)
    login_resp = await authenticate_as(async_client, "till-price@example.com")
    assert login_resp.status_code == 200

    patch_resp = await async_client.patch(
        f"/api/v1/skus/{sku['id']}",
        json={"wholesale_ex_vat": "100.00"},
    )
    assert patch_resp.status_code == 403

    get_resp = await async_client.get(f"/api/v1/skus/{sku['id']}")
    assert get_resp.status_code == 200


async def test_books_cannot_patch_prices_but_can_list(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    await _create_sku(owner_client, "BOOKS")
    await create_test_staff(
        owner_client,
        **{
            "email": "books-price@example.com",
            "password": "books-password",
            "role": "books",
        },
    )

    async_client.cookies.clear()
    async_client.headers.pop("Authorization", None)
    login_resp = await authenticate_as(async_client, "books-price@example.com")
    assert login_resp.status_code == 200

    list_resp = await async_client.get("/api/v1/skus")
    assert list_resp.status_code == 200

    sku_id = list_resp.json()[0]["id"]
    patch_resp = await async_client.patch(
        f"/api/v1/skus/{sku_id}",
        json={"retail_ex_vat": "50.00"},
    )
    assert patch_resp.status_code == 403


async def test_warehouse_cannot_patch_prices(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    sku = await _create_sku(owner_client, "WH")
    await create_test_staff(
        owner_client,
        **{
            "email": "warehouse-price@example.com",
            "password": "warehouse-password",
            "role": "warehouse",
        },
    )

    async_client.cookies.clear()
    async_client.headers.pop("Authorization", None)
    login_resp = await authenticate_as(async_client, "warehouse-price@example.com")
    assert login_resp.status_code == 200

    patch_resp = await async_client.patch(
        f"/api/v1/skus/{sku['id']}",
        json={"wholesale_ex_vat": "100.00"},
    )
    assert patch_resp.status_code == 403


async def test_buyer_can_patch_prices(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    sku = await _create_sku(owner_client, "BUYER")
    await create_test_staff(
        owner_client,
        **{
            "email": "buyer-price@example.com",
            "password": "buyer-password",
            "role": "buyer",
        },
    )

    async_client.cookies.clear()
    async_client.headers.pop("Authorization", None)
    login_resp = await authenticate_as(async_client, "buyer-price@example.com")
    assert login_resp.status_code == 200

    patch_resp = await async_client.patch(
        f"/api/v1/skus/{sku['id']}",
        json={"wholesale_ex_vat": "100.00"},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["wholesale_inc_vat"] == "115.00"


async def test_both_ex_and_inc_wholesale_returns_validation_error(
    owner_client: AsyncClient,
) -> None:
    sku = await _create_sku(owner_client, "BOTH-W")
    resp = await owner_client.patch(
        f"/api/v1/skus/{sku['id']}",
        json={"wholesale_ex_vat": "100.00", "wholesale_inc_vat": "115.00"},
    )
    assert resp.status_code == 400


async def test_negative_price_returns_validation_error(owner_client: AsyncClient) -> None:
    sku = await _create_sku(owner_client, "NEG")
    resp = await owner_client.patch(
        f"/api/v1/skus/{sku['id']}",
        json={"retail_ex_vat": "-1.00"},
    )
    assert resp.status_code == 400


async def test_clear_price_with_null_ex(owner_client: AsyncClient) -> None:
    sku = await _create_sku(owner_client, "CLEAR")
    set_resp = await owner_client.patch(
        f"/api/v1/skus/{sku['id']}",
        json={"retail_ex_vat": "100.00"},
    )
    assert set_resp.status_code == 200

    clear_resp = await owner_client.patch(
        f"/api/v1/skus/{sku['id']}",
        json={"retail_ex_vat": None},
    )
    assert clear_resp.status_code == 200
    body = clear_resp.json()
    assert body["retail_ex_vat"] is None
    assert body["retail_inc_vat"] is None


async def test_list_and_get_include_price_fields(owner_client: AsyncClient) -> None:
    sku = await _create_sku(owner_client, "LIST")
    await owner_client.patch(
        f"/api/v1/skus/{sku['id']}",
        json={"wholesale_ex_vat": "100.00", "retail_inc_vat": "2300.00"},
    )

    get_resp = await owner_client.get(f"/api/v1/skus/{sku['id']}")
    assert get_resp.status_code == 200
    body = get_resp.json()
    assert body["wholesale_inc_vat"] == "115.00"
    assert body["retail_ex_vat"] == "2000.00"

    list_resp = await owner_client.get("/api/v1/skus")
    assert list_resp.status_code == 200
    listed = next(item for item in list_resp.json() if item["id"] == sku["id"])
    assert listed["wholesale_inc_vat"] == "115.00"
    assert listed["retail_ex_vat"] == "2000.00"


async def test_patch_stockist_and_decorator_inc_vat(owner_client: AsyncClient) -> None:
    sku = await _create_sku(owner_client, "TIERS")
    resp = await owner_client.patch(
        f"/api/v1/skus/{sku['id']}",
        json={"stockist_inc_vat": "1150.00", "decorator_ex_vat": "450.00"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["stockist_ex_vat"] == "1000.00"
    assert body["stockist_inc_vat"] == "1150.00"
    assert body["decorator_ex_vat"] == "450.00"
    assert body["decorator_inc_vat"] == "517.50"
    assert body["retail_ex_vat"] is None
    assert body["wholesale_ex_vat"] is None


async def test_both_ex_and_inc_stockist_returns_validation_error(
    owner_client: AsyncClient,
) -> None:
    sku = await _create_sku(owner_client, "BOTH-S")
    resp = await owner_client.patch(
        f"/api/v1/skus/{sku['id']}",
        json={"stockist_ex_vat": "100.00", "stockist_inc_vat": "115.00"},
    )
    assert resp.status_code == 400


async def test_price_preview_uses_saved_stockist_and_prices_the_draft_per_line(
    owner_client: AsyncClient,
) -> None:
    sku = await _create_sku(owner_client, "PREVIEW")
    sku_url = f"/api/v1/skus/{sku['id']}"
    saved = await owner_client.patch(sku_url, json={"stockist_ex_vat": "2099.00"})
    assert saved.status_code == 200, saved.text
    request = {"classification": "Stockist", "quantity": 1}

    preview = await owner_client.post(f"{sku_url}/price-preview", json=request)
    assert preview.status_code == 200, preview.text
    assert Decimal(preview.json()["vat_rate"]) == Decimal("0.15")
    assert preview.json() == {
        "vat_rate": preview.json()["vat_rate"],
        "unit_ex_vat": "2099.00",
        "subtotal_ex_vat": "2099.00",
        "vat_amount": "314.85",
        "total_inc_vat": "2413.85",
        "source": "stockist",
    }

    draft = await owner_client.post(
        f"{sku_url}/price-preview",
        json={**request, "quantity": 3, "price_changes": {"stockist_ex_vat": "0.03"}},
    )
    assert draft.status_code == 200, draft.text
    assert draft.json()["subtotal_ex_vat"] == "0.09"
    assert draft.json()["vat_amount"] == "0.01"
    assert draft.json()["total_inc_vat"] == "0.10"
    reloaded = await owner_client.get(sku_url)
    assert reloaded.json()["stockist_ex_vat"] == "2099.00"
    assert reloaded.json()["updated_at"] == saved.json()["updated_at"]


async def test_price_preview_honours_clear_and_retail_conversion_at_the_team_rate(
    owner_client: AsyncClient,
) -> None:
    sku = await _create_sku(owner_client, "PREVIEW-RETAIL")
    sku_url = f"/api/v1/skus/{sku['id']}"
    prices = await owner_client.patch(
        sku_url, json={"wholesale_ex_vat": "100.00", "retail_ex_vat": "250.00"}
    )
    assert prices.status_code == 200, prices.text
    settings = await owner_client.patch("/api/v1/settings", json={"vat_rate": "0.16"})
    assert settings.status_code == 200, settings.text
    request = {"classification": "Wholesale", "quantity": 2}
    updates = {"wholesale_ex_vat": None, "retail_inc_vat": "116.00"}

    preview = await owner_client.post(
        f"{sku_url}/price-preview", json={**request, "price_changes": updates}
    )
    assert preview.status_code == 200, preview.text
    assert Decimal(preview.json()["vat_rate"]) == Decimal("0.16")
    assert preview.json()["source"] == "retail_fallback"
    assert preview.json()["unit_ex_vat"] == "100.00"
    assert preview.json()["subtotal_ex_vat"] == "200.00"
    assert preview.json()["vat_amount"] == "32.00"
    assert preview.json()["total_inc_vat"] == "232.00"
    reloaded = await owner_client.get(sku_url)
    assert reloaded.json()["wholesale_ex_vat"] == "100.00"
    assert reloaded.json()["retail_ex_vat"] == "250.00"

    saved = await owner_client.patch(sku_url, json=updates)
    assert saved.status_code == 200, saved.text
    preview_after_save = await owner_client.post(f"{sku_url}/price-preview", json=request)
    assert preview_after_save.status_code == 200, preview_after_save.text
    assert preview_after_save.json() == preview.json()


async def test_price_preview_is_available_to_staff_with_catalogue_read_access(
    async_client: AsyncClient, owner_client: AsyncClient
) -> None:
    sku = await _create_sku(owner_client, "PREVIEW-PERMISSION")
    sku_url = f"/api/v1/skus/{sku['id']}"
    payload = {
        "classification": "Decorator",
        "quantity": 1,
        "price_changes": {"decorator_ex_vat": "100.00"},
    }
    async_client.cookies.clear()
    async_client.headers.pop("Authorization", None)
    unauthenticated = await async_client.post(f"{sku_url}/price-preview", json=payload)
    assert unauthenticated.status_code == 401

    email = "warehouse-price-preview@example.com"
    await create_test_staff(owner_client, email=email, role="warehouse")
    assert (await authenticate_as(async_client, email)).status_code == 200
    preview = await async_client.post(f"{sku_url}/price-preview", json=payload)
    assert preview.status_code == 200, preview.text
    assert preview.json()["source"] == "decorator"
    assert preview.json()["total_inc_vat"] == "115.00"
    patch = await async_client.patch(sku_url, json=payload["price_changes"])
    assert patch.status_code == 403


@pytest.mark.parametrize(
    ("overrides", "status"),
    [
        ({}, 400),
        ({"quantity": 0}, 422),
        ({"quantity": 1000}, 422),
        ({"quantity": 1.5}, 422),
        ({"price_changes": {"stockist_ex_vat": "-1.00"}}, 422),
        ({"price_changes": {"stockist_ex_vat": "1.001"}}, 422),
        ({"price_changes": {"stockist_inc_vat": "115.00"}}, 422),
    ],
)
async def test_price_preview_rejects_unavailable_or_invalid_amounts(
    owner_client: AsyncClient, overrides: dict, status: int
) -> None:
    sku = await _create_sku(owner_client, "PREVIEW-INVALID")
    request = {"classification": "Stockist", "quantity": 1, **overrides}
    preview = await owner_client.post(f"/api/v1/skus/{sku['id']}/price-preview", json=request)
    assert preview.status_code == status, preview.text
