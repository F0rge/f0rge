"""S3 catalogue SKUs API tests."""

from __future__ import annotations

from httpx import AsyncClient

# 1x1 PNG
TINY_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


async def test_create_sku_with_supplier_ref_and_photo(owner_client: AsyncClient) -> None:
    create_resp = await owner_client.post(
        "/api/v1/skus",
        json={
            "our_ref": "VEL-001",
            "our_barcode": "BAR-001",
            "name": "Linen sofa",
            "design": "Chester",
            "fabric": "Natural linen",
            "supplier_ref": "SUP-REF-99",
        },
    )
    assert create_resp.status_code == 201
    body = create_resp.json()
    assert body["our_ref"] == "VEL-001"
    assert body["our_barcode"] == "BAR-001"
    assert body["supplier_ref"] == "SUP-REF-99"
    assert body["supplier_ref"] != body["our_barcode"]
    assert body["photo_storage_key"] is None

    photo_resp = await owner_client.post(
        f"/api/v1/skus/{body['id']}/photo",
        files={"photo": ("sku.png", TINY_PNG, "image/png")},
    )
    assert photo_resp.status_code == 200
    assert photo_resp.json()["photo_storage_key"]

    get_photo = await owner_client.get(f"/api/v1/skus/{body['id']}/photo")
    assert get_photo.status_code == 200
    assert get_photo.headers["content-type"].startswith("image/jpeg")


async def test_duplicate_design_fabric_returns_409(owner_client: AsyncClient) -> None:
    first = await owner_client.post(
        "/api/v1/skus",
        json={
            "our_ref": "VEL-002",
            "our_barcode": "BAR-002",
            "name": "Chair A",
            "design": "Wave",
            "fabric": "Velvet blue",
        },
    )
    assert first.status_code == 201

    dup = await owner_client.post(
        "/api/v1/skus",
        json={
            "our_ref": "VEL-003",
            "our_barcode": "BAR-003",
            "name": "Chair B",
            "design": "wave",
            "fabric": "VELVET BLUE",
        },
    )
    assert dup.status_code == 409


async def test_duplicate_our_barcode_returns_409(owner_client: AsyncClient) -> None:
    first = await owner_client.post(
        "/api/v1/skus",
        json={
            "our_ref": "VEL-004",
            "our_barcode": "BAR-DUP",
            "name": "Table",
            "design": "Round",
            "fabric": "Oak",
        },
    )
    assert first.status_code == 201

    dup = await owner_client.post(
        "/api/v1/skus",
        json={
            "our_ref": "VEL-005",
            "our_barcode": "BAR-DUP",
            "name": "Table 2",
            "design": "Square",
            "fabric": "Walnut",
        },
    )
    assert dup.status_code == 409


async def test_till_cannot_create_sku(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    create_user = await owner_client.post(
        "/api/v1/users",
        json={
            "email": "till-skus@example.com",
            "password": "till-password",
            "role": "till",
        },
    )
    assert create_user.status_code == 201

    async_client.cookies.clear()
    login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "till-skus@example.com", "password": "till-password"},
    )
    assert login_resp.status_code == 200

    list_resp = await async_client.get("/api/v1/skus")
    assert list_resp.status_code == 200

    post_resp = await async_client.post(
        "/api/v1/skus",
        json={
            "our_ref": "VEL-TILL",
            "our_barcode": "BAR-TILL",
            "name": "Till item",
            "design": "Till design",
            "fabric": "Till fabric",
        },
    )
    assert post_resp.status_code == 403


async def test_books_can_list_but_not_create_sku(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    create_user = await owner_client.post(
        "/api/v1/users",
        json={
            "email": "books-skus@example.com",
            "password": "books-password",
            "role": "books",
        },
    )
    assert create_user.status_code == 201

    async_client.cookies.clear()
    login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "books-skus@example.com", "password": "books-password"},
    )
    assert login_resp.status_code == 200

    list_resp = await async_client.get("/api/v1/skus")
    assert list_resp.status_code == 200

    post_resp = await async_client.post(
        "/api/v1/skus",
        json={
            "our_ref": "VEL-BOOKS",
            "our_barcode": "BAR-BOOKS",
            "name": "Books item",
            "design": "Books design",
            "fabric": "Books fabric",
        },
    )
    assert post_resp.status_code == 403


async def test_unauthenticated_catalogue_routes_return_401(async_client: AsyncClient) -> None:
    assert (await async_client.get("/api/v1/skus")).status_code == 401
    post_resp = await async_client.post(
        "/api/v1/skus",
        json={
            "our_ref": "VEL-UNAUTH",
            "our_barcode": "BAR-UNAUTH",
            "name": "No auth",
            "design": "X",
            "fabric": "Y",
        },
    )
    assert post_resp.status_code == 401


async def test_create_sku_with_category(owner_client: AsyncClient) -> None:
    create_resp = await owner_client.post(
        "/api/v1/skus",
        json={
            "our_ref": "VEL-CAT-001",
            "our_barcode": "BAR-CAT-001",
            "name": "Dining chair",
            "design": "Classic",
            "fabric": "Leather",
            "category": "Seating",
        },
    )
    assert create_resp.status_code == 201
    body = create_resp.json()
    assert body["category"] == "Seating"

    get_resp = await owner_client.get(f"/api/v1/skus/{body['id']}")
    assert get_resp.status_code == 200
    assert get_resp.json()["category"] == "Seating"


async def test_patch_category_set_and_clear(owner_client: AsyncClient) -> None:
    create_resp = await owner_client.post(
        "/api/v1/skus",
        json={
            "our_ref": "VEL-CAT-002",
            "our_barcode": "BAR-CAT-002",
            "name": "Side table",
            "design": "Round",
            "fabric": "Oak",
            "category": "Dining",
        },
    )
    assert create_resp.status_code == 201
    sku_id = create_resp.json()["id"]

    patch_resp = await owner_client.patch(
        f"/api/v1/skus/{sku_id}",
        json={"category": "Living"},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["category"] == "Living"

    clear_resp = await owner_client.patch(
        f"/api/v1/skus/{sku_id}",
        json={"category": None},
    )
    assert clear_resp.status_code == 200
    assert clear_resp.json()["category"] is None


async def test_list_skus_filter_by_category(owner_client: AsyncClient) -> None:
    for suffix, category in [("A", "Seating"), ("B", "Dining"), ("C", "Seating")]:
        resp = await owner_client.post(
            "/api/v1/skus",
            json={
                "our_ref": f"VEL-CAT-FIL-{suffix}",
                "our_barcode": f"BAR-CAT-FIL-{suffix}",
                "name": f"Filter item {suffix}",
                "design": f"Design {suffix}",
                "fabric": f"Fabric {suffix}",
                "category": category,
            },
        )
        assert resp.status_code == 201

    filtered = await owner_client.get("/api/v1/skus", params={"category": "Seating"})
    assert filtered.status_code == 200
    refs = {item["our_ref"] for item in filtered.json()}
    assert "VEL-CAT-FIL-A" in refs
    assert "VEL-CAT-FIL-C" in refs
    assert "VEL-CAT-FIL-B" not in refs

    case_insensitive = await owner_client.get("/api/v1/skus", params={"category": "seating"})
    assert case_insensitive.status_code == 200
    case_refs = {item["our_ref"] for item in case_insensitive.json()}
    assert "VEL-CAT-FIL-A" in case_refs
    assert "VEL-CAT-FIL-C" in case_refs


async def _kramerville_id(client: AsyncClient) -> str:
    resp = await client.get("/api/v1/locations")
    assert resp.status_code == 200
    for loc in resp.json():
        if loc["name"] == "Kramerville":
            return loc["id"]
    raise AssertionError("Kramerville not found")


async def test_patch_identity_fields_succeeds(owner_client: AsyncClient) -> None:
    create_resp = await owner_client.post(
        "/api/v1/skus",
        json={
            "our_ref": "VEL-ID-001",
            "our_barcode": "BAR-ID-001",
            "name": "Original name",
            "design": "Original design",
            "fabric": "Original fabric",
        },
    )
    assert create_resp.status_code == 201
    sku_id = create_resp.json()["id"]

    patch_resp = await owner_client.patch(
        f"/api/v1/skus/{sku_id}",
        json={
            "name": "Updated name",
            "our_ref": "VEL-ID-001-NEW",
            "our_barcode": "BAR-ID-001-NEW",
        },
    )
    assert patch_resp.status_code == 200
    body = patch_resp.json()
    assert body["name"] == "Updated name"
    assert body["our_ref"] == "VEL-ID-001-NEW"
    assert body["our_barcode"] == "BAR-ID-001-NEW"


async def test_patch_duplicate_our_ref_returns_409(owner_client: AsyncClient) -> None:
    first = await owner_client.post(
        "/api/v1/skus",
        json={
            "our_ref": "VEL-DUP-REF-A",
            "our_barcode": "BAR-DUP-REF-A",
            "name": "First",
            "design": "Dup design A",
            "fabric": "Dup fabric A",
        },
    )
    assert first.status_code == 201

    second = await owner_client.post(
        "/api/v1/skus",
        json={
            "our_ref": "VEL-DUP-REF-B",
            "our_barcode": "BAR-DUP-REF-B",
            "name": "Second",
            "design": "Dup design B",
            "fabric": "Dup fabric B",
        },
    )
    assert second.status_code == 201
    sku_id = second.json()["id"]

    dup = await owner_client.patch(
        f"/api/v1/skus/{sku_id}",
        json={"our_ref": "VEL-DUP-REF-A"},
    )
    assert dup.status_code == 409


async def test_patch_duplicate_design_fabric_returns_409(owner_client: AsyncClient) -> None:
    first = await owner_client.post(
        "/api/v1/skus",
        json={
            "our_ref": "VEL-DUP-DF-A",
            "our_barcode": "BAR-DUP-DF-A",
            "name": "First",
            "design": "Wave",
            "fabric": "Velvet blue",
        },
    )
    assert first.status_code == 201

    second = await owner_client.post(
        "/api/v1/skus",
        json={
            "our_ref": "VEL-DUP-DF-B",
            "our_barcode": "BAR-DUP-DF-B",
            "name": "Second",
            "design": "Other design",
            "fabric": "Other fabric",
        },
    )
    assert second.status_code == 201
    sku_id = second.json()["id"]

    dup = await owner_client.patch(
        f"/api/v1/skus/{sku_id}",
        json={"design": "wave", "fabric": "VELVET BLUE"},
    )
    assert dup.status_code == 409


async def test_delete_unused_sku_returns_204_then_get_404(owner_client: AsyncClient) -> None:
    create_resp = await owner_client.post(
        "/api/v1/skus",
        json={
            "our_ref": "VEL-DEL-001",
            "our_barcode": "BAR-DEL-001",
            "name": "Deletable",
            "design": "Delete design",
            "fabric": "Delete fabric",
        },
    )
    assert create_resp.status_code == 201
    sku_id = create_resp.json()["id"]

    delete_resp = await owner_client.delete(f"/api/v1/skus/{sku_id}")
    assert delete_resp.status_code == 204

    get_resp = await owner_client.get(f"/api/v1/skus/{sku_id}")
    assert get_resp.status_code == 404


async def test_delete_sku_with_opening_stock_returns_409(owner_client: AsyncClient) -> None:
    location_id = await _kramerville_id(owner_client)
    create_resp = await owner_client.post(
        "/api/v1/skus",
        json={
            "our_ref": "VEL-DEL-STOCK",
            "our_barcode": "BAR-DEL-STOCK",
            "name": "Stocked item",
            "design": "Stock design",
            "fabric": "Stock fabric",
            "opening_location_id": location_id,
            "opening_qty": 3,
            "opening_unit_cost_zar": "50.00",
        },
    )
    assert create_resp.status_code == 201
    sku_id = create_resp.json()["id"]

    delete_resp = await owner_client.delete(f"/api/v1/skus/{sku_id}")
    assert delete_resp.status_code == 409


async def test_unauthenticated_delete_returns_401(async_client: AsyncClient) -> None:
    sku_id = "00000000-0000-0000-0000-000000000001"
    delete_resp = await async_client.delete(f"/api/v1/skus/{sku_id}")
    assert delete_resp.status_code == 401


async def test_till_cannot_patch_identity_or_delete(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    create_resp = await owner_client.post(
        "/api/v1/skus",
        json={
            "our_ref": "VEL-TILL-PATCH",
            "our_barcode": "BAR-TILL-PATCH",
            "name": "Till patch target",
            "design": "Till patch design",
            "fabric": "Till patch fabric",
        },
    )
    assert create_resp.status_code == 201
    sku_id = create_resp.json()["id"]

    create_user = await owner_client.post(
        "/api/v1/users",
        json={
            "email": "till-patch-skus@example.com",
            "password": "till-password",
            "role": "till",
        },
    )
    assert create_user.status_code == 201

    async_client.cookies.clear()
    login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "till-patch-skus@example.com", "password": "till-password"},
    )
    assert login_resp.status_code == 200

    patch_resp = await async_client.patch(
        f"/api/v1/skus/{sku_id}",
        json={"name": "Till rename"},
    )
    assert patch_resp.status_code == 403

    delete_resp = await async_client.delete(f"/api/v1/skus/{sku_id}")
    assert delete_resp.status_code == 403


async def test_create_sku_defaults_carton_count_one(owner_client: AsyncClient) -> None:
    resp = await owner_client.post(
        "/api/v1/skus",
        json={
            "our_ref": "VEL-CARTON-DEF",
            "our_barcode": "BAR-CARTON-DEF",
            "name": "Default carton sofa",
            "design": "Carton default",
            "fabric": "Linen",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["carton_count"] == 1
    assert body["is_kit"] is False


async def test_create_sku_rejects_carton_count_zero(owner_client: AsyncClient) -> None:
    resp = await owner_client.post(
        "/api/v1/skus",
        json={
            "our_ref": "VEL-CARTON-ZERO",
            "our_barcode": "BAR-CARTON-ZERO",
            "name": "Zero carton",
            "design": "Carton zero",
            "fabric": "Wool",
            "carton_count": 0,
        },
    )
    assert resp.status_code == 422
