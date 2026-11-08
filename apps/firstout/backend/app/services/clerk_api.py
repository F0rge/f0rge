"""Small injected Clerk BAPI adapter. Never expose upstream bodies or credentials."""

from __future__ import annotations

import asyncio
from typing import Optional
from urllib.parse import quote

import httpx

from app.config import settings
from f0rge_core.exceptions import ConflictError, ExternalServiceError, ValidationError

MAX_MEMBERS = 5


class ClerkAPI:
    def __init__(self, client: httpx.AsyncClient, secret: str) -> None:
        self.client = client
        self.secret = secret

    async def request(self, method: str, path: str, *, payload=None, params=None, missing=False):
        if not self.secret:
            raise ExternalServiceError("Clerk server credentials are not configured")
        for attempt in range(3):
            try:
                response = await self.client.request(
                    method,
                    "https://api.clerk.com/v1" + path,
                    headers={"Authorization": f"Bearer {self.secret}"},
                    json=payload,
                    params=params,
                    timeout=15,
                )
            except httpx.HTTPError as exc:
                raise ExternalServiceError("Clerk is unavailable; retry safely") from exc
            if response.status_code == 429 and attempt < 2:
                await asyncio.sleep(2**attempt)
                continue
            if response.status_code == 404 and missing:
                return None
            if response.status_code in (409, 422):
                raise ConflictError(
                    "Clerk could not create this identity or organisation; review existing records"
                )
            if not response.is_success:
                raise ExternalServiceError("Clerk request failed; retry safely")
            try:
                return response.json() if response.content else {}
            except ValueError as exc:
                raise ExternalServiceError("Clerk returned an invalid response") from exc
        raise ExternalServiceError("Clerk rate limit reached; retry later")

    async def list_all(self, path: str, *, params=None) -> list[dict]:
        items: list[dict] = []
        for offset in range(0, 10000, 100):
            result = await self.request(
                "GET", path, params={**(params or {}), "limit": 100, "offset": offset}
            )
            page = result if isinstance(result, list) else result.get("data", [])
            if not isinstance(page, list):
                raise ExternalServiceError("Clerk returned an invalid list")
            items.extend(page)
            if len(page) < 100:
                return items
        raise ExternalServiceError("Clerk result exceeds the supported directory size")

    async def user(self, subject: str) -> dict:
        return await self.request("GET", "/users/" + quote(subject, safe=""))

    async def organisation(self, org_id: str) -> Optional[dict]:
        return await self.request("GET", "/organizations/" + quote(org_id, safe=""), missing=True)

    async def ensure_organisation(
        self,
        *,
        name: str,
        slug: str,
        created_by: str,
        operation_id: str,
        max_members: int = MAX_MEMBERS,
    ) -> str:
        expected = {"firstout_provisioning_id": operation_id, "firstout_owner_subject": created_by}
        existing = await self.organisation(slug)
        if existing is not None:
            if existing.get("private_metadata", {}) != expected:
                raise ConflictError("Business URL is already in use")
            if existing.get("max_allowed_memberships") != max_members:
                await self.request(
                    "PATCH",
                    f"/organizations/{quote(existing['id'], safe='')}",
                    payload={"max_allowed_memberships": max_members},
                )
            return existing["id"]
        result = await self.request(
            "POST",
            "/organizations",
            payload={
                "name": name,
                "slug": slug,
                "created_by": created_by,
                "max_allowed_memberships": max_members,
                "private_metadata": expected,
            },
        )
        return result["id"]

    async def create_organisation(self, *, name: str, slug: str, created_by: str) -> str:
        result = await self.request(
            "POST",
            "/organizations",
            payload={
                "name": name,
                "slug": slug,
                "created_by": created_by,
                "max_allowed_memberships": MAX_MEMBERS,
            },
        )
        return result["id"]

    async def memberships_for_user(self, subject: str) -> list[dict]:
        return await self.list_all(f"/users/{quote(subject, safe='')}/organization_memberships")

    async def membership(self, org_id: str, subject: str) -> Optional[dict]:
        members = await self.members(org_id)
        return next(
            (
                member
                for member in members
                if member.get("public_user_data", {}).get("user_id") == subject
            ),
            None,
        )

    async def members(self, org_id: str) -> list[dict]:
        return await self.list_all(f"/organizations/{quote(org_id, safe='')}/memberships")

    async def invitations(self, org_id: str) -> list[dict]:
        return await self.list_all(
            f"/organizations/{quote(org_id, safe='')}/invitations", params={"status": "pending"}
        )

    async def invite(self, org_id: str, *, email: str, inviter: str, invitation_id: str) -> dict:
        # Find a previously accepted external side effect before retrying a POST.
        for existing in await self.invitations(org_id):
            if existing.get("public_metadata", {}).get("firstout_invitation_id") == invitation_id:
                return existing
        return await self.request(
            "POST",
            f"/organizations/{quote(org_id, safe='')}/invitations",
            payload={
                "email_address": email,
                "role": "org:member",
                "redirect_url": (settings.public_app_url or "https://app.firstout.co.za").rstrip(
                    "/"
                )
                + "/sign-up",
                "public_metadata": {"firstout_invitation_id": invitation_id},
            },
        )

    async def find_external_user(self, external_id: str) -> Optional[dict]:
        users = await self.list_all("/users", params={"external_id": external_id})
        exact = [user for user in users if user.get("external_id") == external_id]
        if len(exact) > 1:
            raise ConflictError("Clerk external identity is ambiguous")
        return exact[0] if exact else None

    async def revoke_invitation(self, org_id: str, invitation_id: str, requester: str) -> None:
        await self.request(
            "POST",
            f"/organizations/{quote(org_id, safe='')}/invitations/{quote(invitation_id, safe='')}/revoke",
            payload={},
        )

    async def create_user(self, payload: dict) -> str:
        existing = await self.find_external_user(payload["external_id"])
        if existing is not None:
            return existing["id"]
        result = await self.request("POST", "/users", payload=payload)
        return result["id"]

    async def ban_user(self, user_id: str) -> None:
        await self.request("POST", f"/users/{quote(user_id, safe='')}/ban")

    async def create_membership(self, org_id: str, user_id: str, role: str) -> None:
        if await self.membership(org_id, user_id) is None:
            await self.request(
                "POST",
                f"/organizations/{quote(org_id, safe='')}/memberships",
                payload={"user_id": user_id, "role": role},
            )


def verified_primary_email(user: dict) -> str:
    if user.get("banned") or user.get("locked") or user.get("deleted"):
        raise ValidationError("This Clerk account is unavailable")
    primary = user.get("primary_email_address_id")
    for address in user.get("email_addresses", []):
        if (
            address.get("id") == primary
            and address.get("verification", {}).get("status") == "verified"
        ):
            from email_validator import validate_email

            try:
                return validate_email(
                    address["email_address"], check_deliverability=False
                ).normalized.lower()
            except ValueError as exc:
                raise ValidationError("A valid verified email is required") from exc
    raise ValidationError("Verify your primary email before creating or joining a business")
