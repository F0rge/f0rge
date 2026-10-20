"""Customer search and duplicate lookup."""

from __future__ import annotations

from typing import Optional

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer
from app.services.customer_match import national_phone_digits, phone_search_needles


@pytest.mark.no_db
def test_phone_needles_treat_sa_formats_as_equivalent() -> None:
    full = "821234567"
    assert national_phone_digits("082 123 4567") == full
    assert national_phone_digits("+27 (82) 123-4567") == full
    assert national_phone_digits("27821234567") == full
    assert national_phone_digits("0027821234567") == full
    assert "82" in phone_search_needles("+2782")
    assert phone_search_needles("27") == []
    assert phone_search_needles("82") == []


async def _create(
    client: AsyncClient,
    *,
    name: str,
    email: Optional[str] = None,
    phone: Optional[str] = None,
) -> dict:
    body: dict = {"name": name}
    if email is not None:
        body["email"] = email
    if phone is not None:
        body["phone"] = phone
    resp = await client.post("/api/v1/customers", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_search_matches_name_email_and_sa_phone_formats(
    owner_client: AsyncClient,
    async_db: AsyncSession,
) -> None:
    sipho = await _create(
        owner_client,
        name="Sipho Dlamini",
        email="sipho.dlamini@firstout.test",
        phone="082 123 4567",
    )
    lindiwe = await _create(
        owner_client,
        name="Lindiwe Nkosi",
        email="lindiwe@other.test",
        phone="+27 (71) 555-0199",
    )

    stored = (
        await async_db.execute(select(Customer.phone_national).where(Customer.id == sipho["id"]))
    ).scalar_one()
    assert stored == "821234567"

    async def ids_for(q: str) -> set[str]:
        resp = await owner_client.get("/api/v1/customers", params={"q": q})
        assert resp.status_code == 200, resp.text
        return {row["id"] for row in resp.json()}

    assert await ids_for("sipho") == {sipho["id"]}
    assert await ids_for("DLAMINI") == {sipho["id"]}
    assert await ids_for("sipho.dlamini@firstout") == {sipho["id"]}
    assert await ids_for("OTHER.TEST") == {lindiwe["id"]}
    for query in (
        "0821234567",
        "082 123 4567",
        "+27 82 123 4567",
        "+27821234567",
        "27821234567",
        "(082) 123-4567",
        "082-123-4567",
        "123 4567",
    ):
        assert await ids_for(query) == {sipho["id"]}, query
    assert await ids_for("0715550199") == {lindiwe["id"]}
    assert await ids_for("+27715550199") == {lindiwe["id"]}
    assert await ids_for("(071) 555-0199") == {lindiwe["id"]}
    assert sipho["id"] not in await ids_for("nomatchxyz")
    percent = await ids_for("%")
    assert sipho["id"] not in percent
    assert lindiwe["id"] not in percent


async def test_duplicates_match_folded_name_email_and_phone(owner_client: AsyncClient) -> None:
    sipho = await _create(
        owner_client,
        name="Sipho Dlamini",
        email="sipho.dlamini@firstout.test",
        phone="082 123 4567",
    )
    await _create(
        owner_client,
        name="Lindiwe Nkosi",
        email="lindiwe@other.test",
        phone="+27 (71) 555-0199",
    )

    by_name = await owner_client.get(
        "/api/v1/customers/duplicates",
        params={"name": "  sipho   dlamini  "},
    )
    assert by_name.status_code == 200, by_name.text
    assert by_name.json() == [
        {
            "id": sipho["id"],
            "name": "Sipho Dlamini",
            "email": "sipho.dlamini@firstout.test",
            "phone": "082 123 4567",
            "matched_fields": ["name"],
        }
    ]

    by_email = await owner_client.get(
        "/api/v1/customers/duplicates",
        params={"email": "Sipho.Dlamini@Firstout.Test"},
    )
    assert by_email.status_code == 200
    assert by_email.json()[0]["id"] == sipho["id"]
    assert by_email.json()[0]["matched_fields"] == ["email"]

    for phone in ("+27 82 123 4567", "27821234567", "(082) 123-4567", "0027821234567"):
        by_phone = await owner_client.get("/api/v1/customers/duplicates", params={"phone": phone})
        assert by_phone.status_code == 200, phone
        body = by_phone.json()
        assert [row["id"] for row in body] == [sipho["id"]], phone
        assert body[0]["matched_fields"] == ["phone"]

    both = await owner_client.get(
        "/api/v1/customers/duplicates",
        params={"name": "Lindiwe Nkosi", "phone": "0821234567"},
    )
    assert both.status_code == 200
    fields = {row["name"]: row["matched_fields"] for row in both.json()}
    assert fields == {
        "Lindiwe Nkosi": ["name"],
        "Sipho Dlamini": ["phone"],
    }

    empty = await owner_client.get("/api/v1/customers/duplicates")
    assert empty.status_code == 200
    assert empty.json() == []

    missing = await owner_client.get(
        "/api/v1/customers/duplicates",
        params={"name": "Nobody Here", "email": "nope@example.com", "phone": "0830000000"},
    )
    assert missing.status_code == 200
    assert missing.json() == []


async def test_exact_name_duplicate_is_a_clear_conflict(owner_client: AsyncClient) -> None:
    await _create(owner_client, name="Sipho Dlamini")
    clash = await owner_client.post("/api/v1/customers", json={"name": "sipho dlamini"})
    assert clash.status_code == 409
    assert clash.json()["detail"] == "A customer with this name already exists"

    spaced = await owner_client.post("/api/v1/customers", json={"name": "Sipho  Dlamini"})
    assert spaced.status_code == 201, spaced.text
    warned = await owner_client.get(
        "/api/v1/customers/duplicates",
        params={"name": "Sipho Dlamini"},
    )
    assert warned.status_code == 200
    assert len(warned.json()) == 2
    assert all(row["matched_fields"] == ["name"] for row in warned.json())


async def test_customer_search_and_duplicates_require_auth(async_client: AsyncClient) -> None:
    listed = await async_client.get("/api/v1/customers", params={"q": "sipho"})
    dupes = await async_client.get("/api/v1/customers/duplicates", params={"name": "Sipho"})
    assert listed.status_code == 401
    assert dupes.status_code == 401
