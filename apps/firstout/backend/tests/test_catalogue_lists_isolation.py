"""Categories and materials are isolated by RLS, proven as the non-owner runtime role."""

from __future__ import annotations

import pytest
import sqlalchemy as sa
from httpx import ASGITransport, AsyncClient

from f0rge_db.organisation import organisation_session
from tests.test_tenant_database import rls_database_url, tenant_database  # noqa: F401

pytestmark = pytest.mark.no_db


async def test_second_tenant_cannot_see_or_change_lists(tenant_database):  # noqa: F811
    from app.database import get_db
    from app.main import app
    from app.models.membership import Membership
    from app.models.user import User
    from tests.conftest import signed_clerk_token

    admin, _runtime, maker, a, b = tenant_database
    for team in (a, b):
        async with organisation_session(maker, team) as session:
            user = User(
                team_id=team,
                clerk_user_id=f"user-lists-{team.hex}",
                email=f"lists-{team}@example.com",
                password_hash="synthetic",
                role="owner",
            )
            session.add(user)
            await session.flush()
            session.add(
                Membership(
                    user_id=user.id,
                    team_id=team,
                    role="owner",
                    permission_source="legacy",
                    is_legacy_home=True,
                )
            )
            await session.commit()

    def headers(team) -> dict:
        token = signed_clerk_token(
            f"user-lists-{team.hex}", org_id=f"org-proof-{team.hex}", org_slug=f"proof-{team.hex}"
        )
        return {"Authorization": "Bearer " + token}

    async def runtime_get_db():
        async with organisation_session(maker) as session:
            yield session

    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = runtime_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            category = await client.post(
                "/api/v1/categories", json={"name": "Shared name"}, headers=headers(a)
            )
            assert category.status_code == 201, category.text
            material = await client.post(
                "/api/v1/materials",
                json={"name": "Shared name", "family": "other"},
                headers=headers(a),
            )
            assert material.status_code == 201, material.text
            category_id, material_id = category.json()["id"], material.json()["id"]

            seen = await client.get("/api/v1/categories?lifecycle=all", headers=headers(b))
            assert seen.status_code == 200 and category_id not in seen.text
            seen = await client.get("/api/v1/materials?lifecycle=all", headers=headers(b))
            assert seen.status_code == 200 and material_id not in seen.text
            for path in (f"/api/v1/categories/{category_id}", f"/api/v1/materials/{material_id}"):
                changed = await client.patch(path, json={"name": "Taken"}, headers=headers(b))
                assert changed.status_code == 404, changed.text
            child = await client.post(
                "/api/v1/categories",
                json={"name": "Child", "parent_id": category_id},
                headers=headers(b),
            )
            assert child.status_code == 404
            # Names are unique per tenant only: the other tenant's row does not block this one.
            own = await client.post(
                "/api/v1/categories", json={"name": "shared NAME"}, headers=headers(b)
            )
            assert own.status_code == 201, own.text
            own = await client.post(
                "/api/v1/materials",
                json={"name": "Shared name", "family": "wood"},
                headers=headers(b),
            )
            assert own.status_code == 201, own.text

            mine = (await client.get("/api/v1/categories", headers=headers(a))).json()
            assert [row["name"] for row in mine["categories"]] == ["Shared name"]
    finally:
        if previous is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous
        async with admin.begin() as conn:
            for table in ("sku_categories", "materials"):
                await conn.execute(
                    sa.text(f"DELETE FROM {table} WHERE team_id IN (:a,:b)"), {"a": a, "b": b}
                )
