"""Direct SQL RLS policy tests for social tables (issue #308).

Policy assertions run under ``SET ROLE test_app`` inside a rolled-back
superuser transaction so (a) RLS is enforced and (b) seeds do not leak across
tests. Cross-user HTTP flows use the normal ``async_db`` savepoint fixture.
"""

from __future__ import annotations

import importlib.util
import re
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
import sqlalchemy as sa
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncSession

from app.crud.base import unit_of_work
from app.database import get_db
from app.main import app
from app.models.user import LEO_PLACEHOLDER_PASSWORD_HASH
from app.services.notifications import NotificationService
from app.sql.social_functions import NOTIFICATIONS_RLS_SQL
from app.sql.social_rls import (
    CONNECTIONS_RLS_STATEMENTS,
    GROUP_MEMBERS_RLS_STATEMENTS,
    GROUPS_RLS_STATEMENTS,
    MEAL_TAGS_RLS_STATEMENTS,
    NOTIFICATIONS_RLS_STATEMENTS,
    SOCIAL_TABLES,
)
from tests.conftest import TEST_APP_ROLE
from tests.helpers import make_tenant_get_db_override, signup_payload

PASSWORD = "secure-pass-12"

_MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations" / "versions"


def _normalize_sql(sql: str) -> str:
    return re.sub(r"\s+", " ", sql.strip())


def _load_migration_attr(filename: str, attr: str) -> tuple[str, ...]:
    path = _MIGRATIONS_DIR / filename
    spec = importlib.util.spec_from_file_location(f"mig_{filename}", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return getattr(mod, attr)


def _ordered_pair(a: uuid.UUID, b: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID]:
    return (a, b) if a < b else (b, a)


@asynccontextmanager
async def _rls_probe(superuser_engine: AsyncEngine) -> AsyncIterator[AsyncConnection]:
    """Superuser connection with per-test rollback; switch to ``test_app`` via SET ROLE."""
    async with superuser_engine.connect() as conn:
        trans = await conn.begin()
        try:
            yield conn
        finally:
            if trans.is_active:
                await trans.rollback()


async def _set_app_user(conn: AsyncConnection, user_id: uuid.UUID | None) -> None:
    await conn.execute(sa.text(f"SET ROLE {TEST_APP_ROLE}"))
    if user_id is not None:
        await conn.execute(
            sa.text("SELECT set_config('app.user_id', :u, true)"),
            {"u": str(user_id)},
        )


async def _count_visible(
    conn: AsyncConnection,
    table: str,
    user_id: uuid.UUID | None,
    *,
    where: str = "TRUE",
) -> int:
    await _set_app_user(conn, user_id)
    result = await conn.execute(sa.text(f"SELECT count(*) FROM {table} WHERE {where}"))
    return int(result.scalar_one())


async def _insert_users_conn(conn: AsyncConnection, *user_ids: uuid.UUID) -> None:
    for uid in user_ids:
        await conn.execute(
            sa.text(
                """
                INSERT INTO users (id, email, password_hash, avatar_default_index, created_at)
                VALUES (:id, :email, :password_hash, 0, now())
                """
            ),
            {
                "id": uid,
                "email": f"rls-{uid}@example.com",
                "password_hash": LEO_PLACEHOLDER_PASSWORD_HASH,
            },
        )


async def _seed_connection_conn(
    conn: AsyncConnection,
    user_a: uuid.UUID,
    user_b: uuid.UUID,
    *,
    requester: uuid.UUID,
    status: str = "pending",
) -> uuid.UUID:
    low, high = _ordered_pair(user_a, user_b)
    conn_id = uuid.uuid4()
    await conn.execute(
        sa.text(
            """
            INSERT INTO connections
                (id, user_low, user_high, requester_id, status, created_at)
            VALUES (:id, :low, :high, :requester, :status, now())
            """
        ),
        {
            "id": conn_id,
            "low": low,
            "high": high,
            "requester": requester,
            "status": status,
        },
    )
    return conn_id


async def _seed_group_with_invite_conn(
    conn: AsyncConnection,
    owner_id: uuid.UUID,
    invitee_id: uuid.UUID,
) -> uuid.UUID:
    group_id = uuid.uuid4()
    member_id = uuid.uuid4()
    await conn.execute(
        sa.text(
            """
            INSERT INTO groups (id, name, owner_id, created_at)
            VALUES (:id, 'RLS probe group', :owner, now())
            """
        ),
        {"id": group_id, "owner": owner_id},
    )
    await conn.execute(
        sa.text(
            """
            INSERT INTO group_members
                (id, group_id, user_id, role, status, invited_by, created_at)
            VALUES (:id, :gid, :uid, 'member', 'invited', :owner, now())
            """
        ),
        {"id": member_id, "gid": group_id, "uid": invitee_id, "owner": owner_id},
    )
    return group_id


async def _signup_client(async_db: AsyncSession, suffix: str) -> AsyncClient:
    app.dependency_overrides[get_db] = make_tenant_get_db_override(async_db)
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    handle = f"rls_{suffix}"
    resp = await client.post(
        "/api/v1/auth/signup",
        json=signup_payload(f"{handle}@example.com", PASSWORD, handle),
    )
    assert resp.status_code == 200
    return client


# ---------------------------------------------------------------------------
# DDL parity (hygiene)
# ---------------------------------------------------------------------------


def test_social_rls_ddl_matches_migrations() -> None:
    mig_notif = tuple(s.strip() for s in NOTIFICATIONS_RLS_SQL.split(";") if s.strip())
    assert tuple(_normalize_sql(s) for s in NOTIFICATIONS_RLS_STATEMENTS) == tuple(
        _normalize_sql(s) for s in mig_notif
    )
    assert tuple(_normalize_sql(s) for s in CONNECTIONS_RLS_STATEMENTS) == tuple(
        _normalize_sql(s) for s in _load_migration_attr("036_connections.py", "_CONNECTIONS_RLS")
    )
    assert tuple(_normalize_sql(s) for s in GROUPS_RLS_STATEMENTS) == tuple(
        _normalize_sql(s) for s in _load_migration_attr("037_groups.py", "_GROUPS_RLS")
    )
    assert tuple(_normalize_sql(s) for s in GROUP_MEMBERS_RLS_STATEMENTS) == tuple(
        _normalize_sql(s) for s in _load_migration_attr("037_groups.py", "_GROUP_MEMBERS_RLS")
    )
    assert tuple(_normalize_sql(s) for s in MEAL_TAGS_RLS_STATEMENTS) == tuple(
        _normalize_sql(s) for s in _load_migration_attr("038_meal_tags.py", "_MEAL_TAGS_RLS")
    )


# ---------------------------------------------------------------------------
# No GUC
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_social_tables_empty_without_user_guc(superuser_engine: AsyncEngine) -> None:
    """Without ``app.user_id``, social policies hide every row (NULL::uuid comparisons)."""
    user_a, user_b = uuid.uuid4(), uuid.uuid4()
    async with _rls_probe(superuser_engine) as conn:
        await _insert_users_conn(conn, user_a, user_b)
        await _seed_connection_conn(conn, user_a, user_b, requester=user_a)
        await _seed_group_with_invite_conn(conn, user_a, user_b)
        await conn.execute(
            sa.text(
                """
                INSERT INTO notifications (user_id, type, payload, created_at)
                VALUES (:u, 'probe', '{}'::jsonb, now())
                """
            ),
            {"u": user_a},
        )
        await conn.execute(sa.text(f"SET ROLE {TEST_APP_ROLE}"))
        for table in SOCIAL_TABLES:
            try:
                result = await conn.execute(sa.text(f"SELECT count(*) FROM {table}"))
                assert int(result.scalar_one()) == 0
            except DBAPIError as exc:
                # Empty-string GUC poisons uuid casts; still fail-closed (issue #308).
                assert "uuid" in str(exc).lower()
                return


# ---------------------------------------------------------------------------
# connections
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_connections_party_can_see_pair_third_party_cannot(
    superuser_engine: AsyncEngine,
) -> None:
    user_a, user_b, outsider = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    async with _rls_probe(superuser_engine) as conn:
        await _insert_users_conn(conn, user_a, user_b, outsider)
        await _seed_connection_conn(conn, user_a, user_b, requester=user_a)

        assert await _count_visible(conn, "connections", user_a) == 1
        assert await _count_visible(conn, "connections", user_b) == 1
        assert await _count_visible(conn, "connections", outsider) == 0


@pytest.mark.asyncio
async def test_connections_non_requester_can_update_to_accept(
    superuser_engine: AsyncEngine,
) -> None:
    user_a, user_b = uuid.uuid4(), uuid.uuid4()
    async with _rls_probe(superuser_engine) as conn:
        await _insert_users_conn(conn, user_a, user_b)
        conn_id = await _seed_connection_conn(conn, user_a, user_b, requester=user_a)

        await _set_app_user(conn, user_b)
        await conn.execute(
            sa.text(
                """
                UPDATE connections
                SET status = 'accepted', responded_at = now()
                WHERE id = :id
                """
            ),
            {"id": conn_id},
        )

        row = (
            await conn.execute(
                sa.text("SELECT status FROM connections WHERE id = :id"),
                {"id": conn_id},
            )
        ).one()
        assert row.status == "accepted"


@pytest.mark.asyncio
async def test_connections_third_party_cannot_insert(superuser_engine: AsyncEngine) -> None:
    user_a, user_b, outsider = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    low, high = _ordered_pair(user_a, user_b)
    async with _rls_probe(superuser_engine) as conn:
        await _insert_users_conn(conn, user_a, user_b, outsider)
        await _set_app_user(conn, outsider)
        with pytest.raises(DBAPIError):
            await conn.execute(
                sa.text(
                    """
                    INSERT INTO connections
                        (user_low, user_high, requester_id, status, created_at)
                    VALUES (:low, :high, :requester, 'pending', now())
                    """
                ),
                {"low": low, "high": high, "requester": user_a},
            )


# ---------------------------------------------------------------------------
# notifications
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_notifications_direct_cross_user_insert_denied(
    superuser_engine: AsyncEngine,
) -> None:
    sender, recipient = uuid.uuid4(), uuid.uuid4()
    async with _rls_probe(superuser_engine) as conn:
        await _insert_users_conn(conn, sender, recipient)
        await _set_app_user(conn, sender)
        with pytest.raises(DBAPIError):
            await conn.execute(
                sa.text(
                    """
                    INSERT INTO notifications (user_id, type, payload, created_at)
                    VALUES (:recipient, 'probe', '{}'::jsonb, now())
                    """
                ),
                {"recipient": recipient},
            )


@pytest.mark.asyncio
async def test_create_notification_cross_user_succeeds(
    superuser_engine: AsyncEngine,
) -> None:
    sender, recipient = uuid.uuid4(), uuid.uuid4()
    async with _rls_probe(superuser_engine) as conn:
        await _insert_users_conn(conn, sender, recipient)
        await _set_app_user(conn, sender)
        await conn.execute(sa.text("SELECT set_config('app.service_role', 'social_notifier', true)"))
        new_id = (
            await conn.execute(
                sa.text(
                    "SELECT create_notification(:recipient, 'connection_request', "
                    '\'{"handle": "sender"}\'::jsonb)'
                ),
                {"recipient": recipient},
            )
        ).scalar_one()
        assert new_id is not None
        assert await _count_visible(conn, "notifications", recipient) == 1
        assert await _count_visible(conn, "notifications", sender) == 0


# ---------------------------------------------------------------------------
# groups / group_members
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_group_invitee_sees_group_name_non_member_does_not(
    superuser_engine: AsyncEngine,
) -> None:
    owner, invitee, stranger = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    async with _rls_probe(superuser_engine) as conn:
        await _insert_users_conn(conn, owner, invitee, stranger)
        group_id = await _seed_group_with_invite_conn(conn, owner, invitee)

        assert await _count_visible(conn, "groups", invitee, where=f"id = '{group_id}'") == 1
        assert await _count_visible(conn, "groups", stranger, where=f"id = '{group_id}'") == 0


@pytest.mark.asyncio
async def test_group_member_query_no_recursion_error(superuser_engine: AsyncEngine) -> None:
    owner, invitee = uuid.uuid4(), uuid.uuid4()
    async with _rls_probe(superuser_engine) as conn:
        await _insert_users_conn(conn, owner, invitee)
        group_id = await _seed_group_with_invite_conn(conn, owner, invitee)
        await _set_app_user(conn, invitee)
        count = (
            await conn.execute(
                sa.text("SELECT count(*) FROM group_members WHERE group_id = :gid"),
                {"gid": group_id},
            )
        ).scalar_one()
        assert count == 1


# ---------------------------------------------------------------------------
# Account deletion — zero social orphans (hygiene)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_account_cascades_social_rows(
    async_db: AsyncSession,
    superuser_engine: AsyncEngine,
) -> None:
    victim = await _signup_client(async_db, uuid.uuid4().hex[:8])
    friend = await _signup_client(async_db, uuid.uuid4().hex[:8])
    try:
        victim_me = await victim.get("/api/v1/auth/me")
        victim_id = uuid.UUID(victim_me.json()["user_id"])
        friend_handle = (await friend.get("/api/v1/auth/me")).json()["handle"]

        sent = await victim.post("/api/v1/social/connections", json={"handle": friend_handle})
        assert sent.status_code == 201
        conn_id = sent.json()["id"]
        await friend.post(f"/api/v1/social/connections/{conn_id}/accept")

        group = await victim.post("/api/v1/social/groups", json={"name": "delete probe"})
        assert group.status_code == 201
        group_id = group.json()["id"]

        await victim.post(
            f"/api/v1/social/groups/{group_id}/invite",
            json={"handle": friend_handle},
        )

        async with unit_of_work(async_db):
            await NotificationService(async_db).notify(
                victim_id, "connection_request", {"handle": "x"}
            )

        deleted = await victim.request("DELETE", "/api/v1/account", json={"password": PASSWORD})
        assert deleted.status_code == 204

        async with superuser_engine.connect() as conn:
            for table, clause in (
                ("connections", "user_low = :u OR user_high = :u OR requester_id = :u"),
                ("notifications", "user_id = :u"),
                ("groups", "owner_id = :u"),
                ("group_members", "user_id = :u OR invited_by = :u"),
            ):
                count = (
                    await conn.execute(
                        sa.text(f"SELECT count(*) FROM {table} WHERE {clause}"),
                        {"u": victim_id},
                    )
                ).scalar_one()
                assert count == 0, table
    finally:
        await victim.aclose()
        await friend.aclose()
        app.dependency_overrides.pop(get_db, None)
