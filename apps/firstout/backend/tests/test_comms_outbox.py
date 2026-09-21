"""Comms outbox table and send ACL."""

from __future__ import annotations

import uuid

import pytest
from cryptography.fernet import Fernet
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.comms_message import CommsChannel, CommsDocumentType, CommsProvider
from app.services.comms.outbox import CommsOutboxService
from app.services.comms.secrets import decrypt, encrypt


def _doc_query() -> dict[str, str]:
    return {
        "document_type": "invoice",
        "document_id": str(uuid.uuid4()),
    }


async def _login(client: AsyncClient, email: str, password: str) -> AsyncClient:
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return client


async def test_unauthenticated_list_returns_401(async_client: AsyncClient) -> None:
    resp = await async_client.get("/api/v1/comms/messages", params=_doc_query())
    assert resp.status_code == 401


async def test_till_can_list_messages(async_client: AsyncClient) -> None:
    await _login(async_client, "till@example.com", settings.seed_till_password)
    resp = await async_client.get("/api/v1/comms/messages", params=_doc_query())
    assert resp.status_code == 200
    assert resp.json() == []


async def test_books_can_list_messages(async_client: AsyncClient) -> None:
    await _login(async_client, "books@example.com", settings.seed_books_password)
    resp = await async_client.get("/api/v1/comms/messages", params=_doc_query())
    assert resp.status_code == 200
    assert resp.json() == []


async def test_owner_can_list_messages(owner_client: AsyncClient) -> None:
    resp = await owner_client.get("/api/v1/comms/messages", params=_doc_query())
    assert resp.status_code == 200
    assert resp.json() == []


async def test_warehouse_list_returns_403(async_client: AsyncClient) -> None:
    await _login(async_client, "warehouse@example.com", settings.seed_warehouse_password)
    resp = await async_client.get("/api/v1/comms/messages", params=_doc_query())
    assert resp.status_code == 403


async def test_enqueue_then_list(
    async_db: AsyncSession,
    owner_client: AsyncClient,
) -> None:
    document_id = uuid.uuid4()
    outbox = CommsOutboxService(async_db)
    row = await outbox.enqueue(
        channel=CommsChannel.EMAIL,
        provider=CommsProvider.SMTP,
        document_type=CommsDocumentType.INVOICE,
        document_id=document_id,
        to_address="customer@example.com",
        actor_user_id=None,
        from_identity="shop@example.com",
    )
    listed = await owner_client.get(
        "/api/v1/comms/messages",
        params={"document_type": "invoice", "document_id": str(document_id)},
    )
    assert listed.status_code == 200
    body = listed.json()
    assert len(body) == 1
    assert body[0]["id"] == str(row.id)
    assert body[0]["status"] == "pending"
    assert body[0]["to_address"] == "customer@example.com"


async def test_encrypt_round_trip_with_settings_key(monkeypatch: pytest.MonkeyPatch) -> None:
    key = Fernet.generate_key().decode()
    monkeypatch.setattr(settings, "settings_encryption_key", key)
    token = encrypt("keep-secret")
    assert decrypt(token) == "keep-secret"
    assert b"keep-secret" not in token
