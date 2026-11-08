from __future__ import annotations

import base64
import datetime
import json
import hmac
import time
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from starlette.requests import Request
from svix.webhooks import Webhook
from app.config import settings
from app.services.tenant_host import (
    tenant_slug_from_host,
    request_tenant_slug,
    require_matching_host,
)
from app.services.clerk import verify_clerk_token
from app.services.clerk_import import import_staff_user, ImportRateLimited, staff_import_payload
from app.routers.clerk_webhooks import verify_webhook

pytestmark = pytest.mark.no_db


@pytest.mark.parametrize(
    "host",
    [
        "evilfirstout.co.za",
        "a.app.firstout.co.za.evil.com",
        "a.b.app.firstout.co.za",
        "-a.app.firstout.co.za",
        "admin.app.firstout.co.za",
        "API.app.firstout.co.za",
        "a.app.firstout.co.za:443",
        "a.app.firstout.co.za,evil.com",
    ],
)
def test_bad_hosts(host):
    with pytest.raises(HTTPException):
        tenant_slug_from_host(host)


def test_hosts_and_mismatch():
    assert tenant_slug_from_host("firstout.app.firstout.co.za") == "firstout"
    assert tenant_slug_from_host("app.firstout.co.za") is None
    with pytest.raises(HTTPException) as exc:
        require_matching_host("other", "firstout")
    assert exc.value.status_code == 403


def test_proxy_host_secret(monkeypatch):
    monkeypatch.setattr(settings, "tenant_isolation_mode", "enforced")
    monkeypatch.setattr(settings, "frontend_proxy_secret", "synthetic-proxy")
    headers = [
        (b"host", b"api.firstout.co.za"),
        (b"x-firstout-frontend-host", b"firstout.app.firstout.co.za"),
    ]
    request = Request({"type": "http", "headers": headers})
    with pytest.raises(HTTPException):
        request_tenant_slug(request)
    headers.append(
        (
            b"x-firstout-proxy-signature",
            hmac.digest(b"synthetic-proxy", b"firstout.app.firstout.co.za", "sha256")
            .hex()
            .encode(),
        )
    )
    assert request_tenant_slug(Request({"type": "http", "headers": headers})) == "firstout"


@pytest.mark.asyncio
async def test_signed_clerk_jwt_and_bad_signature(monkeypatch):
    from app.services import clerk

    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    monkeypatch.setattr(settings, "tenant_isolation_mode", "enforced")
    monkeypatch.setattr(settings, "clerk_enabled", True)
    monkeypatch.setattr(settings, "clerk_issuer", "https://synthetic.clerk.accounts.dev")
    monkeypatch.setattr(settings, "clerk_authorized_parties", ["https://app.firstout.co.za"])
    monkeypatch.setattr(
        clerk,
        "jwks_client",
        lambda _: SimpleNamespace(
            get_signing_key_from_jwt=lambda _: SimpleNamespace(key=private.public_key())
        ),
    )
    now = int(time.time())
    claims = {
        "iss": settings.clerk_issuer,
        "sub": "user_synthetic",
        "exp": now + 60,
        "iat": now,
        "nbf": now,
        "azp": "https://app.firstout.co.za",
        "o": {"id": "org_synthetic", "slg": "firstout", "rol": "member"},
    }
    identity = await verify_clerk_token(jwt.encode(claims, private, algorithm="RS256"))
    assert identity.org_id == "org_synthetic"
    claims["azp"] = "https://firstout.app.firstout.co.za"
    assert (
        await verify_clerk_token(jwt.encode(claims, private, algorithm="RS256"))
    ).org_slug == "firstout"
    for origin in [
        "https://other.app.firstout.co.za",
        "https://firstout.app.firstout.co.za.evil.example",
        "https://firstout.app.firstout.co.za:444",
    ]:
        claims["azp"] = origin
        with pytest.raises(HTTPException):
            await verify_clerk_token(jwt.encode(claims, private, algorithm="RS256"))
    claims["azp"] = "https://evil.example"
    with pytest.raises(HTTPException):
        await verify_clerk_token(jwt.encode(claims, private, algorithm="RS256"))
    with pytest.raises(HTTPException):
        await verify_clerk_token(
            jwt.encode(claims, "wrong-key-for-synthetic-hmac-test-only", algorithm="HS256")
        )


def test_svix_signature_and_replay_window(monkeypatch):
    secret = "whsec_" + base64.b64encode(b"synthetic-only-webhook-secret").decode()
    monkeypatch.setattr(settings, "clerk_webhook_secret", secret)
    payload = json.dumps({"type": "organizationMembership.deleted", "data": {}})
    now = datetime.datetime.now(datetime.timezone.utc)
    headers = {
        "svix-id": "msg_test",
        "svix-timestamp": str(int(now.timestamp())),
        "svix-signature": Webhook(secret).sign("msg_test", now, payload),
    }
    assert verify_webhook(payload.encode(), headers)["type"] == "organizationMembership.deleted"
    with pytest.raises(HTTPException):
        verify_webhook((payload + " ").encode(), headers)
    headers["svix-timestamp"] = "1"
    with pytest.raises(HTTPException):
        verify_webhook(payload.encode(), headers)


@pytest.mark.asyncio
async def test_import_disabled_and_digest_preserved(monkeypatch):
    from app.services.auth import hash_password, verify_password

    user = SimpleNamespace(
        id=uuid.uuid4(),
        email="synthetic@example.com",
        role="buyer",
        password_hash=hash_password("synthetic-password"),
        is_disabled=True,
        clerk_user_id=None,
    )
    provider = SimpleNamespace(
        create_user=AsyncMock(return_value="user_fake"),
        ban_user=AsyncMock(),
        create_membership=AsyncMock(),
    )
    monkeypatch.setattr(settings, "clerk_import_enabled", False)
    with pytest.raises(RuntimeError):
        await import_staff_user(user, "org_fake", provider)
    provider.create_user.assert_not_called()
    monkeypatch.setattr(settings, "clerk_import_enabled", True)
    provider.create_user.side_effect = [ImportRateLimited(), "user_fake"]
    sleep = AsyncMock()
    assert await import_staff_user(user, "org_fake", provider, sleep=sleep) == "user_fake"
    payload = provider.create_user.call_args.args[0]
    assert payload["external_id"] == str(user.id)
    assert payload["username"] == "fo_" + user.id.hex
    assert provider.create_user.call_args_list[0].args[0] == payload
    assert payload["password_hasher"] == "bcrypt"
    assert verify_password("synthetic-password", payload["password_digest"])
    provider.ban_user.assert_awaited_once_with("user_fake")
    assert user.is_disabled
    sleep.assert_awaited_once_with(1)


def test_staff_import_username_is_stable_when_profile_changes():
    user = SimpleNamespace(
        id=uuid.UUID("42cda4d1-c635-4fa8-8313-b249848ec80c"),
        email="before@example.com",
        password_hash="synthetic-bcrypt-digest",
    )
    first = staff_import_payload(user)
    user.email = "after@example.com"
    second = staff_import_payload(user)
    assert first["username"] == second["username"] == "fo_42cda4d1c6354fa88313b249848ec80c"
    assert len(first["username"]) == 35
    assert first["external_id"] == second["external_id"] == str(user.id)
    assert first["password_digest"] == second["password_digest"] == user.password_hash
    assert first["email_address"] == ["before@example.com"]
    assert second["email_address"] == ["after@example.com"]
    assert first["create_organization_enabled"] is False


async def test_already_linked_staff_does_not_replace_provider_username(monkeypatch):
    from app.services.auth import hash_password

    user = SimpleNamespace(
        id=uuid.uuid4(),
        email="linked@example.com",
        role="buyer",
        password_hash=hash_password("existing-password"),
        is_disabled=False,
        clerk_user_id="user_already_linked",
    )
    provider = SimpleNamespace(
        create_user=AsyncMock(), ban_user=AsyncMock(), create_membership=AsyncMock()
    )
    monkeypatch.setattr(settings, "clerk_import_enabled", True)
    assert await import_staff_user(user, "org_existing", provider) == "user_already_linked"
    provider.create_user.assert_not_called()
    provider.create_membership.assert_awaited_once_with(
        "org_existing", "user_already_linked", "org:member"
    )


def test_permission_inventory_comparison_never_exposes_hashes():
    from app.commands.staff_inventory import compare

    before = [
        {
            "id": "synthetic",
            "team_id": "home",
            "is_disabled": False,
            "token_version": 7,
            "default_location_id": None,
            "permissions": ["custom.existing"],
        }
    ]
    after = [dict(before[0], permissions=["custom.existing", "new.grant"])]
    assert compare(before, after) == []
    assert compare(before, [dict(before[0], permissions=[])])
    assert compare(before, [dict(before[0], token_version=8)])


async def test_pending_no_org_token_is_only_valid_for_identity_onboarding(monkeypatch):
    from app.services import clerk

    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    monkeypatch.setattr(settings, "tenant_isolation_mode", "enforced")
    monkeypatch.setattr(settings, "clerk_enabled", True)
    monkeypatch.setattr(settings, "clerk_issuer", "https://synthetic.clerk.accounts.dev")
    monkeypatch.setattr(settings, "clerk_authorized_parties", ["https://app.firstout.co.za"])
    monkeypatch.setattr(
        clerk,
        "jwks_client",
        lambda _: SimpleNamespace(
            get_signing_key_from_jwt=lambda _: SimpleNamespace(key=private.public_key())
        ),
    )
    now = int(time.time())
    claims = {
        "iss": settings.clerk_issuer,
        "sub": "user_pending",
        "exp": now + 60,
        "iat": now,
        "nbf": now,
        "azp": "https://app.firstout.co.za",
        "sts": "pending",
    }
    token = jwt.encode(claims, private, algorithm="RS256")
    assert (await clerk.verify_clerk_session(token)).user_id == "user_pending"
    with pytest.raises(HTTPException, match="Invalid Clerk session"):
        await clerk.verify_clerk_token(token)
    claims["azp"] = "https://untrusted.example"
    with pytest.raises(HTTPException):
        await clerk.verify_clerk_session(jwt.encode(claims, private, algorithm="RS256"))
