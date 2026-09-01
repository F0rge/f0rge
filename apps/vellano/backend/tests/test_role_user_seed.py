"""Role user seed tests."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.crud.user import UserCRUD
from app.models.user import UserRole
from app.services.role_user_seed import ROLE_USER_SPECS, RoleUserSeedService


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
