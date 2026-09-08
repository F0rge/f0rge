"""S2 locations API tests."""

from __future__ import annotations

from httpx import AsyncClient


async def test_list_locations_includes_seed_rows(owner_client: AsyncClient) -> None:
    resp = await owner_client.get("/api/v1/locations")
    assert resp.status_code == 200
    locations = resp.json()
    names_types = {(loc["name"], loc["type"]) for loc in locations}
    assert ("Kramerville", "warehouse") in names_types
    assert ("Bedfordview", "showroom") in names_types


async def test_create_location(owner_client: AsyncClient) -> None:
    create_resp = await owner_client.post(
        "/api/v1/locations",
        json={"name": "Sandton showroom", "type": "showroom"},
    )
    assert create_resp.status_code == 201
    body = create_resp.json()
    assert body["name"] == "Sandton showroom"
    assert body["type"] == "showroom"
    assert body["is_archived"] is False
    assert body["archived_at"] is None

    list_resp = await owner_client.get("/api/v1/locations")
    assert list_resp.status_code == 200
    names = {loc["name"] for loc in list_resp.json()}
    assert "Sandton showroom" in names


async def test_create_invalid_type_returns_422(owner_client: AsyncClient) -> None:
    resp = await owner_client.post(
        "/api/v1/locations",
        json={"name": "Invalid type", "type": "depot"},
    )
    assert resp.status_code == 422


async def test_rename_location(owner_client: AsyncClient) -> None:
    create_resp = await owner_client.post(
        "/api/v1/locations",
        json={"name": "Rename me", "type": "warehouse"},
    )
    assert create_resp.status_code == 201
    location_id = create_resp.json()["id"]

    patch_resp = await owner_client.patch(
        f"/api/v1/locations/{location_id}",
        json={"name": "Renamed warehouse"},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["name"] == "Renamed warehouse"


async def test_archive_location_still_listed(owner_client: AsyncClient) -> None:
    create_resp = await owner_client.post(
        "/api/v1/locations",
        json={"name": "Archive me", "type": "showroom"},
    )
    assert create_resp.status_code == 201
    location_id = create_resp.json()["id"]

    archive_resp = await owner_client.patch(
        f"/api/v1/locations/{location_id}",
        json={"is_archived": True},
    )
    assert archive_resp.status_code == 200
    archived = archive_resp.json()
    assert archived["is_archived"] is True
    assert archived["archived_at"] is not None

    list_resp = await owner_client.get("/api/v1/locations")
    assert list_resp.status_code == 200
    match = next(loc for loc in list_resp.json() if loc["id"] == location_id)
    assert match["is_archived"] is True


async def test_unauthenticated_get_and_post_return_401(async_client: AsyncClient) -> None:
    get_resp = await async_client.get("/api/v1/locations")
    assert get_resp.status_code == 401

    post_resp = await async_client.post(
        "/api/v1/locations",
        json={"name": "No auth", "type": "warehouse"},
    )
    assert post_resp.status_code == 401


async def test_buyer_can_list_but_not_mutate(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    create_resp = await owner_client.post(
        "/api/v1/users",
        json={
            "email": "buyer-locations@example.com",
            "password": "buyer-password",
            "role": "buyer",
        },
    )
    assert create_resp.status_code == 201

    async_client.cookies.clear()
    login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "buyer-locations@example.com", "password": "buyer-password"},
    )
    assert login_resp.status_code == 200

    list_resp = await async_client.get("/api/v1/locations")
    assert list_resp.status_code == 200

    post_resp = await async_client.post(
        "/api/v1/locations",
        json={"name": "Buyer create", "type": "warehouse"},
    )
    assert post_resp.status_code == 403

    patch_resp = await async_client.patch(
        f"/api/v1/locations/{list_resp.json()[0]['id']}",
        json={"name": "Buyer rename"},
    )
    assert patch_resp.status_code == 403


async def test_till_cannot_mutate_locations(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    create_resp = await owner_client.post(
        "/api/v1/users",
        json={
            "email": "till-locations@example.com",
            "password": "till-password",
            "role": "till",
        },
    )
    assert create_resp.status_code == 201

    async_client.cookies.clear()
    login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "till-locations@example.com", "password": "till-password"},
    )
    assert login_resp.status_code == 200

    list_resp = await async_client.get("/api/v1/locations")
    assert list_resp.status_code == 200

    post_resp = await async_client.post(
        "/api/v1/locations",
        json={"name": "Till create", "type": "showroom"},
    )
    assert post_resp.status_code == 403


async def test_warehouse_role_can_create_location(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    create_user_resp = await owner_client.post(
        "/api/v1/users",
        json={
            "email": "warehouse-locations@example.com",
            "password": "warehouse-password",
            "role": "warehouse",
        },
    )
    assert create_user_resp.status_code == 201

    async_client.cookies.clear()
    login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={
            "email": "warehouse-locations@example.com",
            "password": "warehouse-password",
        },
    )
    assert login_resp.status_code == 200

    create_resp = await async_client.post(
        "/api/v1/locations",
        json={"name": "Warehouse added", "type": "warehouse"},
    )
    assert create_resp.status_code == 201
    assert create_resp.json()["name"] == "Warehouse added"


async def test_duplicate_active_name_returns_409(owner_client: AsyncClient) -> None:
    first_resp = await owner_client.post(
        "/api/v1/locations",
        json={"name": "Unique Place", "type": "showroom"},
    )
    assert first_resp.status_code == 201

    dup_resp = await owner_client.post(
        "/api/v1/locations",
        json={"name": "unique place", "type": "warehouse"},
    )
    assert dup_resp.status_code == 409


async def test_reuse_name_after_archive_succeeds(owner_client: AsyncClient) -> None:
    create_resp = await owner_client.post(
        "/api/v1/locations",
        json={"name": "Reusable Name", "type": "warehouse"},
    )
    assert create_resp.status_code == 201
    location_id = create_resp.json()["id"]

    archive_resp = await owner_client.patch(
        f"/api/v1/locations/{location_id}",
        json={"is_archived": True},
    )
    assert archive_resp.status_code == 200

    recreate_resp = await owner_client.post(
        "/api/v1/locations",
        json={"name": "Reusable Name", "type": "showroom"},
    )
    assert recreate_resp.status_code == 201
    assert recreate_resp.json()["name"] == "Reusable Name"
    assert recreate_resp.json()["type"] == "showroom"
    assert recreate_resp.json()["is_archived"] is False
