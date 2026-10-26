"""Admin Cin7 import jobs: auth, dry-run rollback, and the commit gate."""

from __future__ import annotations

import io
import stat
import uuid
import zipfile
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cin7_import_run import Cin7ImportRun
from app.models.sku import Sku
from app.models.user import User
from app.services.cin7_import.archive import (
    MAX_UPLOAD_BYTES,
    MIN_UPLOAD_LIMIT_BYTES,
    _check_member,
    extract_zip,
    locate_export_dir,
    pack_export_files,
    validate_zip,
)
from app.services.cin7_import.parse import price_warnings, read_csv_records
from f0rge_core.exceptions import ValidationError
from tests.conftest import OWNER_EMAIL
from tests.test_cin7_import import _fixture_dir
from tests.test_records_api import _login_as

PRICE_FIXTURE = Path(__file__).parent / "fixtures" / "cin7_inventory_prices.csv"
# Counted by price_warnings on the trimmed InventoryList (price columns only).
PRICE_FIXTURE_ROWS = 4964
PRICE_FIXTURE_MISSING = 878
PRICE_FIXTURE_ODD = 749


@pytest.fixture(autouse=True)
def _inline_cin7_jobs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.cin7_import_jobs.run_inline", True)


def _zip_dir(root: Path) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
        for path in sorted(root.iterdir()):
            if path.is_file():
                archive.write(path, f"cin7-export/{path.name}")
    return buffer.getvalue()


def _upload(data: bytes, name: str = "export.zip") -> dict[str, tuple[str, bytes, str]]:
    return {"file": (name, data, "application/zip")}


async def _sku_count(db: AsyncSession) -> int:
    count = await db.scalar(select(func.count()).select_from(Sku))
    return int(count or 0)


async def _chair(db: AsyncSession) -> Sku | None:
    return await db.scalar(select(Sku).where(Sku.our_ref == "CHAIR-1"))


async def test_anonymous_upload_is_rejected(async_client: AsyncClient, tmp_path: Path) -> None:
    data = _zip_dir(_fixture_dir(tmp_path / "export"))
    response = await async_client.post("/api/v1/cin7-imports", files=_upload(data))
    assert response.status_code == 401


async def test_buyer_cannot_list_imports(owner_client: AsyncClient) -> None:
    buyer = await _login_as(owner_client, "buyer")
    response = await buyer.get("/api/v1/cin7-imports")
    assert response.status_code == 403


async def test_dry_run_rolls_back_and_reports(
    owner_client: AsyncClient, async_db: AsyncSession, tmp_path: Path
) -> None:
    before = await _sku_count(async_db)
    data = _zip_dir(_fixture_dir(tmp_path / "export"))
    response = await owner_client.post("/api/v1/cin7-imports", files=_upload(data))
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["status"] == "completed"
    assert body["mode"] == "dry_run"
    assert body["error_count"] == 0
    assert body["warning_count"] == 5
    assert body["summary"]["price_changes"]["stockist"] == 3
    assert body["summary"]["entities"]["sku"]["created"] == 3
    assert body["summary"]["generated_barcodes"] == 2
    assert body["summary"]["generated_barcodes_blank"] == 1
    assert body["summary"]["generated_barcodes_shared"] == 1
    assert await _sku_count(async_db) == before
    assert await _chair(async_db) is None

    warnings = await owner_client.get(f"/api/v1/cin7-imports/{body['id']}/warnings.csv")
    assert warnings.status_code == 200
    assert "missing_tier" in warnings.text
    barcodes = await owner_client.get(f"/api/v1/cin7-imports/{body['id']}/barcodes.csv")
    assert barcodes.status_code == 200
    assert "CHAIR-1,blank,CIN7-CHAIR-1" in barcodes.text
    assert "VASE-1,shared,CIN7-VASE-1" in barcodes.text
    assert "LAMP-1" not in barcodes.text
    history = await owner_client.get("/api/v1/cin7-imports")
    assert history.status_code == 200
    assert any(row["id"] == body["id"] for row in history.json())

    async_db.expire_all()
    stored = await async_db.get(Cin7ImportRun, uuid.UUID(body["id"]))
    assert stored is not None
    assert stored.storage_key
    assert stored.user_email == OWNER_EMAIL


async def test_folder_upload_dry_run(
    owner_client: AsyncClient, async_db: AsyncSession, tmp_path: Path
) -> None:
    root = _fixture_dir(tmp_path / "export")
    files = [
        ("files", (path.name, path.read_bytes(), "text/csv"))
        for path in sorted(root.iterdir())
        if path.is_file()
    ]
    before = await _sku_count(async_db)
    response = await owner_client.post("/api/v1/cin7-imports", files=files)
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["status"] == "completed"
    assert body["error_count"] == 0
    assert body["file_name"] == "cin7-export.zip"
    assert await _sku_count(async_db) == before


async def test_commit_gate(
    owner_client: AsyncClient, async_db: AsyncSession, tmp_path: Path
) -> None:
    data = _zip_dir(_fixture_dir(tmp_path / "export"))
    dry = await owner_client.post("/api/v1/cin7-imports", files=_upload(data))
    assert dry.status_code == 202, dry.text
    body = dry.json()
    assert body["error_count"] == 0
    run_id = body["id"]
    digest = body["file_sha256"]

    missing = await owner_client.post(
        f"/api/v1/cin7-imports/{uuid.uuid4()}/commit",
        json={"file_sha256": digest},
    )
    assert missing.status_code == 404

    wrong = await owner_client.post(
        f"/api/v1/cin7-imports/{run_id}/commit",
        json={"file_sha256": "0" * 64},
    )
    assert wrong.status_code == 409

    committed = await owner_client.post(
        f"/api/v1/cin7-imports/{run_id}/commit",
        json={"file_sha256": digest},
    )
    assert committed.status_code == 202, committed.text
    assert committed.json()["status"] == "completed"
    assert committed.json()["mode"] == "commit"
    chair = await _chair(async_db)
    assert chair is not None
    assert chair.name == "Chair"

    async_db.expire_all()
    dry_row = await async_db.get(Cin7ImportRun, uuid.UUID(run_id))
    commit_row = await async_db.get(Cin7ImportRun, uuid.UUID(committed.json()["id"]))
    assert dry_row is not None and dry_row.storage_key is None
    assert commit_row is not None and commit_row.storage_key is None

    again = await owner_client.post(
        f"/api/v1/cin7-imports/{run_id}/commit",
        json={"file_sha256": digest},
    )
    assert again.status_code in {400, 409}


async def test_commit_rejects_a_dry_run_with_errors(
    owner_client: AsyncClient, tmp_path: Path
) -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("cin7-export/Notes.csv", "A\n1\n")
    response = await owner_client.post(
        "/api/v1/cin7-imports", files=_upload(buffer.getvalue(), "notes.zip")
    )
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["status"] == "failed"
    assert body["error_count"] >= 1
    errors = await owner_client.get(f"/api/v1/cin7-imports/{body['id']}/errors.csv")
    assert errors.status_code == 200
    assert "InventoryList" in errors.text
    rejected = await owner_client.post(
        f"/api/v1/cin7-imports/{body['id']}/commit",
        json={"file_sha256": body["file_sha256"]},
    )
    assert rejected.status_code == 409


async def test_commit_rejects_when_data_was_imported_since(
    owner_client: AsyncClient, async_db: AsyncSession, tmp_path: Path
) -> None:
    data = _zip_dir(_fixture_dir(tmp_path / "export"))
    dry = await owner_client.post("/api/v1/cin7-imports", files=_upload(data))
    body = dry.json()
    owner = await async_db.scalar(select(User).where(User.email == OWNER_EMAIL))
    assert owner is not None
    dry_row = await async_db.get(Cin7ImportRun, uuid.UUID(body["id"]))
    assert dry_row is not None and dry_row.finished_at is not None
    async_db.add(
        Cin7ImportRun(
            user_id=owner.id,
            user_email=owner.email,
            file_sha256="a" * 64,
            file_name="earlier.zip",
            storage_key=None,
            mode="commit",
            status="completed",
            finished_at=dry_row.finished_at,
            summary={},
            warnings=[],
            errors=[],
            warning_count=0,
            error_count=0,
            active_lock=None,
        )
    )
    await async_db.flush()
    rejected = await owner_client.post(
        f"/api/v1/cin7-imports/{body['id']}/commit",
        json={"file_sha256": body["file_sha256"]},
    )
    assert rejected.status_code == 409
    assert await _chair(async_db) is None


async def test_second_job_is_rejected_while_one_is_active(
    owner_client: AsyncClient, async_db: AsyncSession, tmp_path: Path
) -> None:
    owner = await async_db.scalar(select(User).where(User.email == OWNER_EMAIL))
    assert owner is not None
    async_db.add(
        Cin7ImportRun(
            user_id=owner.id,
            user_email=owner.email,
            file_sha256="b" * 64,
            file_name="running.zip",
            storage_key="cin7-imports/running.zip",
            mode="dry_run",
            status="running",
            summary={},
            warnings=[],
            errors=[],
            warning_count=0,
            error_count=0,
            active_lock=True,
        )
    )
    await async_db.flush()
    data = _zip_dir(_fixture_dir(tmp_path / "export"))
    response = await owner_client.post("/api/v1/cin7-imports", files=_upload(data))
    assert response.status_code == 409


@pytest.mark.no_db
def test_upload_limit_is_at_least_25mb() -> None:
    assert MAX_UPLOAD_BYTES >= MIN_UPLOAD_LIMIT_BYTES
    assert MAX_UPLOAD_BYTES >= 25 * 1024 * 1024


@pytest.mark.no_db
def test_zip_rejects_traversal_symlink_and_bomb(tmp_path: Path) -> None:
    escaped = io.BytesIO()
    with zipfile.ZipFile(escaped, "w") as archive:
        archive.writestr("../InventoryList.csv", "ProductCode\nX\n")
    with pytest.raises(ValidationError, match="escapes"):
        validate_zip(escaped.getvalue())

    link = zipfile.ZipInfo("cin7-export/InventoryList.csv")
    link.external_attr = (stat.S_IFLNK | 0o777) << 16
    link.file_size = 4
    link.compress_size = 4
    with pytest.raises(ValidationError, match="symlink"):
        _check_member(link)

    encrypted = zipfile.ZipInfo("cin7-export/InventoryList.csv")
    encrypted.flag_bits = 1
    encrypted.file_size = 4
    encrypted.compress_size = 4
    with pytest.raises(ValidationError, match="encrypted"):
        _check_member(encrypted)

    bomb = io.BytesIO()
    with zipfile.ZipFile(bomb, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("cin7-export/InventoryList.csv", b"0" * (2 * 1024 * 1024))
    with pytest.raises(ValidationError, match="zip bomb"):
        validate_zip(bomb.getvalue())

    nested = tmp_path / "nested"
    (nested / "cin7-export").mkdir(parents=True)
    (nested / "cin7-export" / "InventoryList.csv").write_text("ProductCode\nX\n", encoding="utf-8")
    (nested / "ignore.txt").write_text("no", encoding="utf-8")
    packed = io.BytesIO()
    with zipfile.ZipFile(packed, "w") as archive:
        archive.write(nested / "cin7-export" / "InventoryList.csv", "cin7-export/InventoryList.csv")
    dest = tmp_path / "out"
    extract_zip(packed.getvalue(), dest)
    assert locate_export_dir(dest) == dest / "cin7-export"
    assert not (dest / "ignore.txt").exists()


@pytest.mark.no_db
def test_sample_price_fixture_parses(tmp_path: Path) -> None:
    rows, _shifted = read_csv_records(PRICE_FIXTURE)
    assert len(rows) == PRICE_FIXTURE_ROWS
    warnings = [item for row in rows for item in price_warnings(row)]
    missing = sum(1 for item in warnings if item["kind"] == "missing_tier")
    odd = sum(1 for item in warnings if item["kind"] == "odd_price")
    assert missing == PRICE_FIXTURE_MISSING
    assert odd == PRICE_FIXTURE_ODD
    assert missing > 800

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(PRICE_FIXTURE, "cin7-export/InventoryList.csv")
    dest = tmp_path / "sample"
    extract_zip(buffer.getvalue(), dest)
    extracted, _shifted = read_csv_records(locate_export_dir(dest) / "InventoryList.csv")
    assert len(extracted) == PRICE_FIXTURE_ROWS
    assert extracted[0]["ProductCode"] == rows[0]["ProductCode"]


@pytest.mark.no_db
def test_loose_files_pack_to_a_stable_hash() -> None:
    first = pack_export_files([("B.csv", b"b\n"), ("A.csv", b"a\n")])
    second = pack_export_files([("A.csv", b"a\n"), ("B.csv", b"b\n")])
    assert first == second
    with pytest.raises(ValidationError, match="not a csv"):
        pack_export_files([("notes.txt", b"nope")])
