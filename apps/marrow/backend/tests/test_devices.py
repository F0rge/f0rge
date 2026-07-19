"""Tests for APNs device registration + push delivery (#391).

Registration/unregistration go through the HTTP API with real signed-up
users; cross-user behavior there is enforced by explicit user scoping in the
service. The RLS policies themselves (tenant_isolation + device_registrar)
are asserted under ``SET ROLE test_app`` like test_social_rls, because the
savepoint session's engine is the container superuser and bypasses RLS.
Push delivery reuses the reminder-tick cross-session pattern from
test_reminders with a fake APNs client patched into ``app.services.push``.
"""

from __future__ import annotations

import datetime
import uuid
from types import SimpleNamespace

import pytest
import pytest_asyncio
import sqlalchemy as sa
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

import app.services.push as push
from app.config import settings
from app.models.user import LEO_PLACEHOLDER_PASSWORD_HASH
from app.services.reminders import run_reminder_tick
from tests.conftest import TEST_APP_ROLE
from tests.helpers import create_treatment, signup_client

UTC = datetime.timezone.utc
# Europe/Luxembourg is UTC+2 (CEST) on this date: 09:05 local — slot 1 in window.
IN_WINDOW = datetime.datetime(2026, 7, 18, 7, 5, tzinfo=UTC)

TOKEN_A = "a" * 64
TOKEN_B = "b" * 64


class FakeAPNs:
    def __init__(self, status: str = "200", description: str | None = None) -> None:
        self.status = status
        self.description = description
        self.sent: list = []

    async def send_notification(self, request):
        self.sent.append(request)
        return SimpleNamespace(
            notification_id="fake", status=self.status, description=self.description
        )


@pytest.fixture
def fake_apns(monkeypatch: pytest.MonkeyPatch) -> FakeAPNs:
    fake = FakeAPNs()
    monkeypatch.setattr(push, "_get_client", lambda: fake)
    return fake


@pytest_asyncio.fixture
async def signed_up_client(async_db: AsyncSession) -> AsyncClient:
    return await signup_client(async_db, f"dev_{uuid.uuid4().hex[:8]}@example.com")


async def _register(client: AsyncClient, token: str, **extra) -> dict:
    resp = await client.post("/api/v1/devices", json={"token": token, **extra})
    assert resp.status_code == 200
    return resp.json()


# ---------------------------------------------------------------------------
# Registration / unregistration
# ---------------------------------------------------------------------------


async def test_register_is_idempotent(signed_up_client: AsyncClient):
    first = await _register(signed_up_client, TOKEN_A)
    assert first["token"] == TOKEN_A
    assert first["platform"] == "ios"

    second = await _register(signed_up_client, TOKEN_A)
    assert second["id"] == first["id"]


async def test_unregister_own_token(signed_up_client: AsyncClient):
    await _register(signed_up_client, TOKEN_A, platform="ios")

    resp = await signed_up_client.delete(f"/api/v1/devices/{TOKEN_A}")
    assert resp.status_code == 204

    resp = await signed_up_client.delete(f"/api/v1/devices/{TOKEN_A}")
    assert resp.status_code == 404


async def test_cannot_delete_other_users_token(async_db: AsyncSession):
    client_a = await signup_client(async_db, f"dev_{uuid.uuid4().hex[:8]}@example.com")
    client_b = await signup_client(async_db, f"dev_{uuid.uuid4().hex[:8]}@example.com")
    await _register(client_a, TOKEN_A)

    # B cannot delete A's token — 404, and A's row survives.
    resp = await client_b.delete(f"/api/v1/devices/{TOKEN_A}")
    assert resp.status_code == 404
    resp = await client_a.delete(f"/api/v1/devices/{TOKEN_A}")
    assert resp.status_code == 204


async def test_device_tokens_rls_policies(superuser_engine: AsyncEngine):
    """tenant_isolation hides other users' rows; device_registrar crosses tenants."""
    user_a, user_b = uuid.uuid4(), uuid.uuid4()
    async with superuser_engine.connect() as conn:
        trans = await conn.begin()
        try:
            for uid in (user_a, user_b):
                await conn.execute(
                    sa.text(
                        "INSERT INTO users (id, email, password_hash, avatar_default_index, "
                        "created_at) VALUES (:id, :email, :ph, 0, now())"
                    ),
                    {
                        "id": uid,
                        "email": f"rls-{uid}@example.com",
                        "ph": LEO_PLACEHOLDER_PASSWORD_HASH,
                    },
                )
            await conn.execute(
                sa.text("INSERT INTO device_tokens (user_id, token) VALUES (:u, :t)"),
                [{"u": user_a, "t": "tok-a"}, {"u": user_b, "t": "tok-b"}],
            )

            await conn.execute(sa.text(f"SET ROLE {TEST_APP_ROLE}"))
            await conn.execute(
                sa.text("SELECT set_config('app.user_id', :u, true)"), {"u": str(user_a)}
            )
            visible = (await conn.execute(sa.text("SELECT token FROM device_tokens"))).scalars()
            assert list(visible) == ["tok-a"]

            # A cannot touch B's row...
            result = await conn.execute(sa.text("DELETE FROM device_tokens WHERE token = 'tok-b'"))
            assert result.rowcount == 0
            # ...until the device_registrar service role is assumed (takeover path).
            await conn.execute(
                sa.text("SELECT set_config('app.service_role', 'device_registrar', true)")
            )
            result = await conn.execute(sa.text("DELETE FROM device_tokens WHERE token = 'tok-b'"))
            assert result.rowcount == 1
        finally:
            if trans.is_active:
                await trans.rollback()


async def test_token_takeover_moves_row_to_new_user(async_db: AsyncSession):
    """Beatriz signs in on a phone previously registered to Leo."""
    client_a = await signup_client(async_db, f"dev_{uuid.uuid4().hex[:8]}@example.com")
    client_b = await signup_client(async_db, f"dev_{uuid.uuid4().hex[:8]}@example.com")
    await _register(client_a, TOKEN_A)

    taken_over = await _register(client_b, TOKEN_A)
    assert taken_over["token"] == TOKEN_A

    # The row now belongs to B: A gets a 404, B can delete it.
    resp = await client_a.delete(f"/api/v1/devices/{TOKEN_A}")
    assert resp.status_code == 404
    resp = await client_b.delete(f"/api/v1/devices/{TOKEN_A}")
    assert resp.status_code == 204


# ---------------------------------------------------------------------------
# Push delivery from the reminder tick
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("patch_reminder_session_maker")
async def test_fired_reminder_pushes_to_registered_device(
    signed_up_client: AsyncClient, fake_apns: FakeAPNs
):
    treatment_id = await create_treatment(signed_up_client)
    await _register(signed_up_client, TOKEN_A)

    assert await run_reminder_tick(now=IN_WINDOW) == 1

    assert len(fake_apns.sent) == 1
    request = fake_apns.sent[0]
    assert request.device_token == TOKEN_A
    aps = request.message["aps"]
    assert aps["alert"]["title"] == "Dose reminder"
    assert "Rifaximin" in aps["alert"]["body"]
    assert aps["category"] == "DOSE_REMINDER"
    assert request.message["treatment_id"] == str(treatment_id)
    assert request.message["slot"] == 1
    assert request.message["date"] == "2026-07-18"

    # Dedupe-losing second tick: no second push.
    assert await run_reminder_tick(now=IN_WINDOW) == 0
    assert len(fake_apns.sent) == 1


@pytest.mark.usefixtures("patch_reminder_session_maker")
async def test_gone_result_prunes_token(signed_up_client: AsyncClient, fake_apns: FakeAPNs):
    fake_apns.status = "410"
    fake_apns.description = "Unregistered"
    await create_treatment(signed_up_client)
    await _register(signed_up_client, TOKEN_B)

    assert await run_reminder_tick(now=IN_WINDOW) == 1
    assert len(fake_apns.sent) == 1

    # Row was pruned — unregistering it now 404s.
    resp = await signed_up_client.delete(f"/api/v1/devices/{TOKEN_B}")
    assert resp.status_code == 404


@pytest.mark.usefixtures("patch_reminder_session_maker")
async def test_user_without_tokens_still_gets_in_app_row(
    signed_up_client: AsyncClient, fake_apns: FakeAPNs
):
    await create_treatment(signed_up_client)

    assert await run_reminder_tick(now=IN_WINDOW) == 1
    assert fake_apns.sent == []

    notes = await signed_up_client.get("/api/v1/notifications")
    assert len(notes.json()) == 1


async def test_unconfigured_apns_builds_no_client(
    async_db: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    import aioapns

    for field in ("apns_key_id", "apns_team_id", "apns_private_key"):
        monkeypatch.setattr(settings, field, "")
    monkeypatch.setattr(push, "_client", None)

    def _fail(*args, **kwargs):
        raise AssertionError("APNs client constructed despite empty settings")

    monkeypatch.setattr(aioapns, "APNs", _fail)

    # No-op, no client, no crash.
    await push.send_dose_reminder(async_db, uuid.uuid4(), [{"treatment_name": "x", "slot": 1}])
    assert push._client is None
