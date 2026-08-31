"""Tests for GET /labs/{id}/attachment — stream bytes, never presign."""

from __future__ import annotations

import datetime
import io
import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession

from botocore.exceptions import ClientError
from f0rge_db.tenant import apply_session_user_id
from app.config import settings
from app.models.lab import Lab
from app.services.labs import LAB_ATTACHMENT_CACHE_CONTROL
from tests.helpers import signup_client

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def authed_user_id(authed_client: AsyncClient) -> uuid.UUID:
    resp = await authed_client.get("/api/v1/auth/me")
    assert resp.status_code == 200
    return uuid.UUID(resp.json()["user_id"])


def _png_bytes() -> bytes:
    img = Image.new("RGB", (64, 48), color="green")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _pdf_bytes() -> bytes:
    return b"%PDF-1.4\n% dummy lab report\n"


async def _make_lab(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    attachment_path: str | None,
    source_kind: str = "image",
    lab_type: str = "imaging",
) -> Lab:
    await apply_session_user_id(db, user_id)
    lab = Lab(
        user_id=user_id,
        lab_date=datetime.date(2026, 5, 15),
        name="MRI lumbar",
        type=lab_type,
        source_kind=source_kind,
        attachment_path=attachment_path,
    )
    db.add(lab)
    await db.commit()
    await db.refresh(lab)
    return lab


def _s3_404(operation: str) -> ClientError:
    return ClientError(
        {
            "Error": {"Code": "404", "Message": "Not Found"},
            "ResponseMetadata": {"HTTPStatusCode": 404},
        },
        operation,
    )


class _MemoryS3:
    """In-memory S3 for lab attachment serve tests (GET bytes, never 307)."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.get_calls: list[str] = []
        self.presign_calls: list[str] = []

    def get_object(self, Bucket: str, Key: str) -> dict:  # noqa: N803
        self.get_calls.append(Key)
        if Key not in self.objects:
            raise _s3_404("GetObject")
        return {"Body": io.BytesIO(self.objects[Key])}

    def generate_presigned_url(
        self,
        ClientMethod: str,  # noqa: N803
        Params: dict,
        ExpiresIn: int,  # noqa: N803
    ) -> str:
        self.presign_calls.append(Params["Key"])
        return f"https://storage.test/{Params['Bucket']}/{Params['Key']}?e={ExpiresIn}"


async def test_local_disk_png_returns_bytes(
    async_db: AsyncSession,
    authed_client: AsyncClient,
    authed_user_id: uuid.UUID,
    tmp_path,
) -> None:
    png = _png_bytes()
    rel = tmp_path / "lab_attachments" / "2026-05" / "abc123def456.png"
    rel.parent.mkdir(parents=True)
    rel.write_bytes(png)

    lab = await _make_lab(async_db, authed_user_id, attachment_path=str(rel))

    resp = await authed_client.get(f"/api/v1/labs/{lab.id}/attachment", follow_redirects=False)
    assert resp.status_code == 200
    assert resp.headers.get("cache-control") == LAB_ATTACHMENT_CACHE_CONTROL
    assert resp.headers.get("content-type", "").startswith("image/png")
    assert resp.content == png
    assert "inline" in resp.headers.get("content-disposition", "")


async def test_local_disk_pdf_returns_bytes(
    async_db: AsyncSession,
    authed_client: AsyncClient,
    authed_user_id: uuid.UUID,
    tmp_path,
) -> None:
    pdf = _pdf_bytes()
    rel = tmp_path / "lab_attachments" / "2026-05" / "deadbeef.pdf"
    rel.parent.mkdir(parents=True)
    rel.write_bytes(pdf)

    lab = await _make_lab(
        async_db,
        authed_user_id,
        attachment_path=str(rel),
        source_kind="pdf",
        lab_type="blood",
    )

    resp = await authed_client.get(f"/api/v1/labs/{lab.id}/attachment", follow_redirects=False)
    assert resp.status_code == 200
    assert resp.headers.get("content-type", "").startswith("application/pdf")
    assert resp.content == pdf


async def test_remote_key_streams_without_redirect(
    async_db: AsyncSession,
    authed_client: AsyncClient,
    authed_user_id: uuid.UUID,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services import object_storage

    monkeypatch.setattr(settings, "bucket_name", "test-bucket")
    monkeypatch.setattr(settings, "aws_access_key_id", "test-key")
    monkeypatch.setattr(settings, "aws_secret_access_key", "test-secret")
    monkeypatch.setattr(settings, "aws_endpoint_url_s3", "http://storage.test")

    stub = _MemoryS3()
    monkeypatch.setattr(object_storage, "_s3_client", lambda: stub)

    key = f"{authed_user_id}/lab_attachments/2026-08/{'a' * 40}.png"
    png = _png_bytes()
    stub.objects[key] = png

    lab = await _make_lab(async_db, authed_user_id, attachment_path=key)

    resp = await authed_client.get(f"/api/v1/labs/{lab.id}/attachment", follow_redirects=False)
    assert resp.status_code == 200
    assert resp.headers.get("cache-control") == LAB_ATTACHMENT_CACHE_CONTROL
    assert resp.headers.get("content-type", "").startswith("image/png")
    assert resp.content == png
    assert stub.presign_calls == []
    assert stub.get_calls == [key]


async def test_unauthenticated_returns_401(async_client: AsyncClient) -> None:
    resp = await async_client.get("/api/v1/labs/1/attachment", follow_redirects=False)
    assert resp.status_code == 401


async def test_missing_attachment_path_returns_404(
    async_db: AsyncSession,
    authed_client: AsyncClient,
    authed_user_id: uuid.UUID,
) -> None:
    lab = await _make_lab(async_db, authed_user_id, attachment_path=None)

    resp = await authed_client.get(f"/api/v1/labs/{lab.id}/attachment", follow_redirects=False)
    assert resp.status_code == 404


async def test_other_users_lab_returns_404(
    async_db: AsyncSession,
    authed_client: AsyncClient,
    authed_user_id: uuid.UUID,
    tmp_path,
) -> None:
    png = _png_bytes()
    rel = tmp_path / "lab_attachments" / "2026-05" / "other-user.png"
    rel.parent.mkdir(parents=True)
    rel.write_bytes(png)

    other_client = await signup_client(async_db, f"lab-other-{uuid.uuid4().hex[:8]}@example.com")
    other_me = await other_client.get("/api/v1/auth/me")
    other_user_id = uuid.UUID(other_me.json()["user_id"])

    lab = await _make_lab(async_db, other_user_id, attachment_path=str(rel))

    resp = await authed_client.get(f"/api/v1/labs/{lab.id}/attachment", follow_redirects=False)
    assert resp.status_code == 404


async def test_download_query_sets_attachment_disposition(
    async_db: AsyncSession,
    authed_client: AsyncClient,
    authed_user_id: uuid.UUID,
    tmp_path,
) -> None:
    png = _png_bytes()
    rel = tmp_path / "lab_attachments" / "2026-05" / "download-me.png"
    rel.parent.mkdir(parents=True)
    rel.write_bytes(png)

    lab = await _make_lab(async_db, authed_user_id, attachment_path=str(rel))

    resp = await authed_client.get(
        f"/api/v1/labs/{lab.id}/attachment?download=true",
        follow_redirects=False,
    )
    assert resp.status_code == 200
    disposition = resp.headers.get("content-disposition", "")
    assert disposition.startswith("attachment;")
    assert 'filename="download-me.png"' in disposition
