"""Document numbering via document_sequences."""

from __future__ import annotations

import asyncio

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.user import TeamCRUD
from app.services.document_numbering import DocumentNumberingService


@pytest.mark.asyncio
async def test_allocate_returns_inv_0001_then_0002(async_db: AsyncSession) -> None:
    team = await TeamCRUD(async_db).get_first()
    assert team is not None
    numbering = DocumentNumberingService(async_db)
    await numbering.ensure_all_for_team(team.id)

    first = await numbering.allocate("invoice", team_id=team.id)
    second = await numbering.allocate("invoice", team_id=team.id)

    assert first == "INV-0001"
    assert second == "INV-0002"


@pytest.mark.asyncio
async def test_concurrent_allocate_does_not_collide(
    async_engine,
    async_db: AsyncSession,
) -> None:
    team = await TeamCRUD(async_db).get_first()
    assert team is not None

    from sqlalchemy.ext.asyncio import async_sessionmaker

    maker = async_sessionmaker(async_engine, expire_on_commit=False, class_=AsyncSession)

    async def _allocate_one() -> str:
        async with maker() as session:
            async with session.begin():
                return await DocumentNumberingService(session).allocate(
                    "transfer",
                    team_id=team.id,
                )

    first, second = await asyncio.gather(_allocate_one(), _allocate_one())
    assert first != second
    assert {first, second} == {"TRF-0001", "TRF-0002"}


async def test_prefix_change_uses_new_prefix_on_next_invoice(
    owner_client: AsyncClient,
) -> None:
    customer = await owner_client.post("/api/v1/customers", json={"name": "Prefix Customer"})
    assert customer.status_code == 201
    customer_id = customer.json()["id"]

    first = await owner_client.post(
        "/api/v1/invoices",
        json={
            "customer_id": customer_id,
            "issue_date": "2026-09-01",
            "lines": [{"description": "Chair", "qty": 1, "unit_ex_vat": "100.00"}],
        },
    )
    assert first.status_code == 201
    assert first.json()["invoice_number"] == "INV-0001"

    patch = await owner_client.patch(
        "/api/v1/settings",
        json={
            "document_sequences": [{"doc_type": "invoice", "prefix": "TAX"}],
        },
    )
    assert patch.status_code == 200

    second = await owner_client.post(
        "/api/v1/invoices",
        json={
            "customer_id": customer_id,
            "issue_date": "2026-09-02",
            "lines": [{"description": "Table", "qty": 1, "unit_ex_vat": "200.00"}],
        },
    )
    assert second.status_code == 201
    assert second.json()["invoice_number"] == "TAX-0002"
    assert first.json()["invoice_number"] == "INV-0001"
