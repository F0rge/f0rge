"""Role user seed tests."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.crud.user import UserCRUD
from app.models.user import UserRole
from app.services.locations import LocationSeedService
from app.services.role_user_seed import ROLE_USER_SPECS, RoleUserSeedService
from app.services.user_default_location import bedfordview_default_location_id


@pytest.mark.parametrize(
    ("email", "role", "password_setting"),
    ROLE_USER_SPECS,
)
async def test_role_users_exist_after_session_seed(
    async_client: AsyncClient,
    email: str,
    role: UserRole,
    password_setting: str,
) -> None:
    password = getattr(settings, password_setting)
    resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 200
    me_resp = await async_client.get("/api/v1/auth/me")
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == email
    assert me_resp.json()["role"] == role.value


async def test_till_seed_user_has_bedfordview_default(async_client: AsyncClient) -> None:
    password = settings.seed_till_password
    login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "till@example.com", "password": password},
    )
    assert login_resp.status_code == 200

    locations_resp = await async_client.get("/api/v1/locations")
    assert locations_resp.status_code == 200
    bedford_id = next(loc["id"] for loc in locations_resp.json() if loc["name"] == "Bedfordview")

    me_resp = await async_client.get("/api/v1/auth/me")
    assert me_resp.status_code == 200
    assert me_resp.json()["default_location_id"] == bedford_id


async def test_role_user_seed_is_idempotent(async_db: AsyncSession) -> None:
    service = RoleUserSeedService(async_db)
    user_crud = UserCRUD(async_db)

    await service.seed()
    first_ids = {
        spec[0]: (await user_crud.get_by_email(spec[0])).id  # type: ignore[union-attr]
        for spec in ROLE_USER_SPECS
    }

    await service.seed()
    assert await user_crud.count() >= 5

    for email, role, _password_setting in ROLE_USER_SPECS:
        user = await user_crud.get_by_email(email)
        assert user is not None
        assert user.role == role
        assert user.id == first_ids[email]

    role_emails = {spec[0] for spec in ROLE_USER_SPECS}
    role_users = [user for user in await user_crud.list_all() if user.email in role_emails]
    assert len(role_users) == 4


async def test_role_user_seed_backfills_null_till_default(async_db: AsyncSession) -> None:
    await LocationSeedService(async_db).seed_if_empty()
    user_crud = UserCRUD(async_db)
    till_user = await user_crud.get_by_email("till@example.com")
    assert till_user is not None
    till_user.default_location_id = None
    await user_crud.commit_refresh(till_user)

    bedford_id = await bedfordview_default_location_id(async_db)
    assert bedford_id is not None

    await RoleUserSeedService(async_db).seed()

    reloaded = await user_crud.get_by_email("till@example.com")
    assert reloaded is not None
    assert reloaded.default_location_id == bedford_id
