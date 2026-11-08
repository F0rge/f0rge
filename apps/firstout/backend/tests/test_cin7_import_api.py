"""Admin Cin7 import jobs: auth, dry-run rollback, and the commit gate."""

from __future__ import annotations

import datetime
import io
import logging
import os
import stat
import uuid
import zipfile
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.cin7_import_run import Cin7ImportRunCRUD
from app.models.cin7_import_run import Cin7ImportRun
from app.models.sku import Sku
from app.models.user import User
from app.services.cin7_import_jobs import Cin7ImportJobService
from app.services.object_storage import save_bytes
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

# Invented prices. Missing cells, amounts below 1, and a retail figure that does
# not survive inc-to-ex and back (100.01 -> 100.02). Not a real catalogue.
PRICE_FIXTURE_CSV = """ProductCode,PriceTier1,PriceTier2,PriceTier3,PriceTier4
TEST-001,100.00,80.00,70.00,1150.00
TEST-002,0,80.00,70.00,1150.00
TEST-003,100.00,,70.00,1150.00
TEST-004,100.00,80.00,0,1150.00
TEST-005,100.00,80.00,70.00,
TEST-006,0.50,80.00,70.00,1150.00
TEST-007,100.00,0.01,70.00,1150.00
TEST-008,100.00,80.00,70.00,0.40
TEST-009,100.00,80.00,70.00,100.01
TEST-010,0,0,0,0
TEST-011,10.00,20.00,30.00,11.50
TEST-012,100.00,80.00,0.87,1150.00
"""
PRICE_FIXTURE_ROWS = 12
PRICE_FIXTURE_MISSING = 8
PRICE_FIXTURE_ODD = 5


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
    fixture = tmp_path / "prices.csv"
    fixture.write_text(PRICE_FIXTURE_CSV, encoding="utf-8")
    rows, _shifted = read_csv_records(fixture)
    assert len(rows) == PRICE_FIXTURE_ROWS
    assert rows[0]["ProductCode"] == "TEST-001"
    warnings = [item for row in rows for item in price_warnings(row)]
    missing = sum(1 for item in warnings if item["kind"] == "missing_tier")
    odd = sum(1 for item in warnings if item["kind"] == "odd_price")
    assert missing == PRICE_FIXTURE_MISSING
    assert odd == PRICE_FIXTURE_ODD
    assert any(
        item["product_code"] == "TEST-009" and "round-trip" in item["detail"] for item in warnings
    )
    assert any(
        item["product_code"] == "TEST-006" and item["kind"] == "odd_price" for item in warnings
    )

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(fixture, "cin7-export/InventoryList.csv")
    dest = tmp_path / "sample"
    extract_zip(buffer.getvalue(), dest)
    extracted, _shifted = read_csv_records(locate_export_dir(dest) / "InventoryList.csv")
    assert len(extracted) == PRICE_FIXTURE_ROWS
    assert extracted[0]["ProductCode"] == "TEST-001"


@pytest.mark.no_db
def test_loose_files_pack_to_a_stable_hash() -> None:
    first = pack_export_files([("B.csv", b"b\n"), ("A.csv", b"a\n")])
    second = pack_export_files([("A.csv", b"a\n"), ("B.csv", b"b\n")])
    assert first == second
    with pytest.raises(ValidationError, match="not a csv"):
        pack_export_files([("notes.txt", b"nope")])


def _stored(name: str, payload: bytes) -> str:
    return save_bytes(f"cin7-imports/{name}.zip", payload)


def _audit_row(owner: User, **overrides: object) -> Cin7ImportRun:
    values: dict[str, object] = {
        "user_id": owner.id,
        "user_email": owner.email,
        "file_sha256": "c" * 64,
        "file_name": "export.zip",
        "storage_key": None,
        "mode": "dry_run",
        "status": "completed",
        "summary": {},
        "warnings": [],
        "errors": [],
        "warning_count": 0,
        "error_count": 0,
        "barcode_replacements": [],
        "active_lock": None,
    }
    values.update(overrides)
    return Cin7ImportRun(**values)


async def test_startup_fails_abandoned_jobs_and_purges_uploads(
    async_db: AsyncSession, caplog: pytest.LogCaptureFixture
) -> None:
    owner = await async_db.scalar(select(User).where(User.email == OWNER_EMAIL))
    assert owner is not None
    running_file = _stored("running", b"running")
    queued_file = _stored("queued", b"queued")
    failed_file = _stored("failed", b"failed")
    kept_file = _stored("kept", b"kept")
    old_file = _stored("old", b"old")
    running = _audit_row(
        owner,
        file_sha256="d" * 64,
        status="running",
        storage_key=running_file,
        active_lock=True,
    )
    queued = _audit_row(
        owner,
        file_sha256="e" * 64,
        status="queued",
        storage_key=queued_file,
        active_lock=None,
    )
    failed = _audit_row(
        owner,
        file_sha256="f" * 64,
        status="failed",
        storage_key=failed_file,
        error_count=1,
        errors=[{"message": "InventoryList file not found"}],
    )
    kept = _audit_row(owner, file_sha256="1" * 64, storage_key=kept_file)
    shared = _audit_row(
        owner,
        file_sha256="1" * 64,
        mode="commit",
        status="failed",
        storage_key=kept_file,
        error_count=1,
        errors=[{"message": "boom"}],
    )
    old = _audit_row(
        owner,
        file_sha256="2" * 64,
        storage_key=old_file,
        created_at=datetime.datetime.utcnow() - datetime.timedelta(days=8),
    )
    async_db.add_all([running, queued, failed, kept, shared, old])
    await async_db.flush()
    running_id, queued_id = running.id, queued.id
    failed_id, kept_id = failed.id, kept.id
    shared_id, old_id = shared.id, old.id

    with caplog.at_level(logging.WARNING, logger="app.services.cin7_import_jobs"):
        await Cin7ImportJobService(async_db).recover_on_startup()

    async_db.expire_all()
    assert "interrupted by restart" in caplog.text
    for row_id in (running_id, queued_id):
        fresh = await async_db.get(Cin7ImportRun, row_id)
        assert fresh is not None
        assert fresh.status == "failed"
        assert fresh.active_lock is None
        assert fresh.errors == [{"message": "interrupted by restart"}]
        assert fresh.storage_key is None
    assert not os.path.exists(running_file)
    assert not os.path.exists(queued_file)
    assert not os.path.exists(failed_file)
    failed_fresh = await async_db.get(Cin7ImportRun, failed_id)
    assert failed_fresh is not None and failed_fresh.storage_key is None
    kept_fresh = await async_db.get(Cin7ImportRun, kept_id)
    assert kept_fresh is not None and kept_fresh.storage_key == kept_file
    assert os.path.exists(kept_file)
    shared_fresh = await async_db.get(Cin7ImportRun, shared_id)
    assert shared_fresh is not None and shared_fresh.storage_key is None
    old_fresh = await async_db.get(Cin7ImportRun, old_id)
    assert old_fresh is not None and old_fresh.storage_key is None
    assert not os.path.exists(old_file)


async def test_busy_lock_rejects_a_second_upload_without_waiting(
    owner_client: AsyncClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _refuse_lock(self: Cin7ImportRunCRUD) -> bool:
        return False

    monkeypatch.setattr(Cin7ImportRunCRUD, "try_lock", _refuse_lock)
    data = _zip_dir(_fixture_dir(tmp_path / "export"))
    response = await owner_client.post("/api/v1/cin7-imports", files=_upload(data))
    assert response.status_code == 409
    assert response.json()["detail"] == "A Cin7 import is already running"
