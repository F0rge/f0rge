from __future__ import annotations

import json

import httpx
import pytest

from app.services.clerk_api import ClerkAPI, verified_primary_email
from f0rge_core.exceptions import ConflictError, ExternalServiceError, ValidationError

pytestmark = pytest.mark.no_db


async def test_membership_uses_documented_collection_and_exact_subject():
    requests = []

    def handler(request):
        requests.append(request)
        assert request.url.path == "/v1/organizations/org_safe/memberships"
        assert request.headers["authorization"] == "Bearer synthetic-server-key"
        return httpx.Response(
            200,
            json={
                "data": [
                    {"id": "om_other", "public_user_data": {"user_id": "user_other"}},
                    {"id": "om_expected", "public_user_data": {"user_id": "user_exact"}},
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = ClerkAPI(client, "synthetic-server-key")
        assert (await provider.membership("org_safe", "user_exact"))["id"] == "om_expected"
        assert await provider.membership("org_safe", "user_missing") is None
    assert len(requests) == 2


async def test_organisation_recovery_rejects_unrelated_provider_org():
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "id": "org_unrelated",
                    "private_metadata": {"firstout_provisioning_id": "someone-else"},
                },
            )
        )
    ) as client:
        with pytest.raises(ConflictError):
            await ClerkAPI(client, "synthetic-key").ensure_organisation(
                name="Business",
                slug="business",
                created_by="user_exact",
                operation_id="operation-exact",
            )


async def test_create_organisation_seeds_only_five_members_and_recovery_marker():
    requests = []

    def handler(request):
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(404)
        assert request.url.path == "/v1/organizations"
        payload = json.loads(request.content)
        assert payload == {
            "name": "New business",
            "slug": "new-business",
            "created_by": "user_owner",
            "max_allowed_memberships": 5,
            "private_metadata": {
                "firstout_provisioning_id": "attempt-id",
                "firstout_owner_subject": "user_owner",
            },
        }
        return httpx.Response(200, json={"id": "org_new"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        assert (
            await ClerkAPI(client, "synthetic-key").ensure_organisation(
                name="New business",
                slug="new-business",
                created_by="user_owner",
                operation_id="attempt-id",
            )
            == "org_new"
        )
    assert [request.method for request in requests] == ["GET", "POST"]


async def test_import_transport_recovers_only_exact_external_uuid_not_email():
    seen = []

    def handler(request):
        seen.append(request)
        assert request.method == "GET"
        assert request.url.path == "/v1/users"
        assert request.url.params["external_id[]"] == "immutable-local-uuid"
        return httpx.Response(
            200, json=[{"id": "user_existing", "external_id": "immutable-local-uuid"}]
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        assert (
            await ClerkAPI(client, "synthetic-key").create_user(
                {"external_id": "immutable-local-uuid", "email_address": ["private@example.com"]}
            )
            == "user_existing"
        )
    assert len(seen) == 1


async def test_provider_errors_never_echo_sensitive_payload_or_upstream_body():
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                500, json={"error": "secret-user@example.com synthetic-password-digest"}
            )
        )
    ) as client:
        with pytest.raises(ExternalServiceError) as exc:
            await ClerkAPI(client, "synthetic-server-key").create_user(
                {"external_id": "uuid", "password_digest": "synthetic-password-digest"}
            )
        assert "synthetic-password" not in str(exc.value)
        assert "secret-user" not in str(exc.value)


def test_verified_email_must_be_primary_and_available():
    profile = {
        "primary_email_address_id": "email_primary",
        "email_addresses": [
            {
                "id": "email_secondary",
                "email_address": "verified@example.com",
                "verification": {"status": "verified"},
            },
            {
                "id": "email_primary",
                "email_address": "primary@example.com",
                "verification": {"status": "unverified"},
            },
        ],
    }
    with pytest.raises(ValidationError):
        verified_primary_email(profile)
    profile["email_addresses"][1]["verification"]["status"] = "verified"
    assert verified_primary_email(profile) == "primary@example.com"
    profile["banned"] = True
    with pytest.raises(ValidationError):
        verified_primary_email(profile)


async def test_invite_uses_server_authority_without_coarse_admin_impersonation():
    requests = []

    def handler(request):
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(200, json={"data": []})
        assert request.url.path == "/v1/organizations/org_home/invitations"
        payload = json.loads(request.content)
        assert "inviter_user_id" not in payload
        assert payload["role"] == "org:member"
        assert payload["public_metadata"] == {"firstout_invitation_id": "local-invite-uuid"}
        return httpx.Response(200, json={"id": "orginv_sent"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await ClerkAPI(client, "synthetic-key").invite(
            "org_home",
            email="staff@example.com",
            inviter="coarse-member-local-owner",
            invitation_id="local-invite-uuid",
        )
        assert result["id"] == "orginv_sent"
    assert len(requests) == 2
