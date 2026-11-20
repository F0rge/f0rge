"""Sale hold time setting (till_hold_hours), spec #979 / ticket #982."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.conftest import authenticate_as


async def test_till_hold_hours_defaults_to_three(owner_client: AsyncClient) -> None:
    resp = await owner_client.get("/api/v1/settings")
    assert resp.status_code == 200
    assert resp.json()["till_hold_hours"] == 3


@pytest.mark.parametrize("hours", [1, 5, 24])
async def test_till_hold_hours_valid_update_persists(owner_client: AsyncClient, hours: int) -> None:
    resp = await owner_client.patch("/api/v1/settings", json={"till_hold_hours": hours})
    assert resp.status_code == 200
    assert resp.json()["till_hold_hours"] == hours
    again = await owner_client.get("/api/v1/settings")
    assert again.json()["till_hold_hours"] == hours


@pytest.mark.parametrize("bad", [0, 25, -1, 2.5, "3", True])
async def test_till_hold_hours_rejects_out_of_range_and_non_integers(
    owner_client: AsyncClient, bad: object
) -> None:
    resp = await owner_client.patch("/api/v1/settings", json={"till_hold_hours": bad})
    assert resp.status_code in (400, 422)
    assert (await owner_client.get("/api/v1/settings")).json()["till_hold_hours"] == 3


async def test_books_cannot_change_till_hold_hours(async_client: AsyncClient) -> None:
    async_client.cookies.clear()
    async_client.headers.pop("Authorization", None)
    assert (await authenticate_as(async_client, "books@example.com")).status_code == 200
    resp = await async_client.patch("/api/v1/settings", json={"till_hold_hours": 5})
    assert resp.status_code == 403
