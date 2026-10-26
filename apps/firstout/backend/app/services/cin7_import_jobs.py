"""Admin Cin7 import jobs.

Dry-run is the default and rolls the import back. Commit is a second job that
must name a completed dry run of the same file hash, with no errors, and no
successful import newer than that dry run. The check runs again inside the
commit transaction. One job at a time.
"""

from __future__ import annotations

import asyncio
import csv
import datetime
import io
import logging
import tempfile
import uuid
from pathlib import Path
from typing import Optional

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.cin7_import_run import Cin7ImportRunCRUD
from app.models.cin7_import_run import Cin7ImportRun
from app.models.user import User
from app.services.cin7_import.archive import (
    extract_zip,
    locate_export_dir,
    pack_export_files,
    sha256_hex,
    validate_zip,
)
from app.services.cin7_import.load import run_import
from app.services.cin7_import.parse import find_file
from app.services.cin7_import.report import ImportReport
from app.services.object_storage import delete_object, read_bytes, save_bytes
from f0rge_core.exceptions import ConflictError, NotFoundError, ValidationError
from f0rge_db.crud import unit_of_work

logger = logging.getLogger(__name__)

# Tests set this so the request session finishes the job before the response.
run_inline = False
_background_tasks: set[asyncio.Task[None]] = set()

RETENTION = datetime.timedelta(days=7)
STALE_AFTER = datetime.timedelta(hours=2)
MAX_STORED_MESSAGES = 5000
_READ_CHUNK = 1024 * 1024


def _now() -> datetime.datetime:
    return datetime.datetime.utcnow()


def _safe_message(exc: BaseException) -> str:
    text = str(exc).replace("\n", " ").strip() or exc.__class__.__name__
    return text[:500]


def _delete_quiet(storage_key: str) -> None:
    try:
        delete_object(storage_key)
    except Exception:
        logger.warning("cin7 import upload delete failed")


def _summary(report: ImportReport) -> dict[str, object]:
    entities = {
        name: {
            "created": result.created,
            "updated": result.updated,
            "unchanged": result.unchanged,
            "skipped": result.skipped,
        }
        for name, result in report.entities.items()
    }
    rows = report.barcode_replacements
    return {
        "entities": entities,
        "price_changes": dict(report.price_changes),
        "generated_barcodes": len(rows),
        "generated_barcodes_blank": sum(1 for row in rows if row.get("reason") == "blank"),
        "generated_barcodes_shared": sum(1 for row in rows if row.get("reason") == "shared"),
    }


def _csv(rows: list[dict[str, str]], columns: list[str]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({column: row.get(column, "") for column in columns})
    return buffer.getvalue()


def _spawn(job_id: uuid.UUID) -> None:
    task = asyncio.create_task(_run_detached(job_id))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


async def _run_detached(job_id: uuid.UUID) -> None:
    from app.database import async_session_maker

    try:
        async with async_session_maker() as session:
            await Cin7ImportJobService(session).execute(job_id)
    except Exception:
        logger.exception("cin7 import job failed to start")


class Cin7ImportJobService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = Cin7ImportRunCRUD(db)

    async def list_runs(self) -> list[Cin7ImportRun]:
        return await self.crud.list_recent(50)

    async def get_run(self, run_id: uuid.UUID) -> Cin7ImportRun:
        row = await self.crud.get(run_id)
        if row is None:
            raise NotFoundError("Cin7 import not found")
        return row

    async def warnings_csv(self, run_id: uuid.UUID) -> str:
        row = await self.get_run(run_id)
        return _csv(
            list(row.warnings or []),
            ["kind", "product_code", "tier", "detail"],
        )

    async def errors_csv(self, run_id: uuid.UUID) -> str:
        row = await self.get_run(run_id)
        return _csv(list(row.errors or []), ["message"])

    async def barcodes_csv(self, run_id: uuid.UUID) -> str:
        row = await self.get_run(run_id)
        return _csv(
            list(row.barcode_replacements or []),
            ["product_code", "reason", "generated_barcode"],
        )

    async def start_dry_run(
        self,
        file: Optional[UploadFile],
        files: Optional[list[UploadFile]],
        user_id: uuid.UUID,
    ) -> Cin7ImportRun:
        data, filename = await self._read_upload(file, files)
        digest = sha256_hex(data)
        job_id = uuid.uuid4()
        storage_key = await asyncio.to_thread(save_bytes, f"cin7-imports/{job_id}.zip", data)
        try:
            await self._enqueue(
                job_id=job_id,
                user_id=user_id,
                file_sha256=digest,
                file_name=filename[:255],
                storage_key=storage_key,
                mode="dry_run",
                dry_run_id=None,
            )
        except Exception:
            await asyncio.to_thread(_delete_quiet, storage_key)
            raise
        await self._kick(job_id)
        return await self._reload(job_id)

    async def start_commit(
        self,
        dry_run_id: uuid.UUID,
        file_sha256: str,
        user_id: uuid.UUID,
    ) -> Cin7ImportRun:
        dry = await self.get_run(dry_run_id)
        await self._reject_unless_committable(dry, file_sha256.strip().lower())
        job_id = uuid.uuid4()
        await self._enqueue(
            job_id=job_id,
            user_id=user_id,
            file_sha256=dry.file_sha256,
            file_name=dry.file_name,
            storage_key=dry.storage_key or "",
            mode="commit",
            dry_run_id=dry.id,
        )
        await self._kick(job_id)
        return await self._reload(job_id)

    async def _reload(self, job_id: uuid.UUID) -> Cin7ImportRun:
        self.db.expire_all()
        return await self.get_run(job_id)

    async def execute(self, job_id: uuid.UUID) -> None:
        async with unit_of_work(self.db):
            await self.crud.acquire_lock()
            job = await self.crud.get(job_id)
            if job is None or job.status != "queued":
                return
            job.status = "running"
            job.updated_at = _now()
        await self._finish(job_id)

    async def _kick(self, job_id: uuid.UUID) -> None:
        if run_inline:
            await self.execute(job_id)
            return
        _spawn(job_id)

    async def _enqueue(
        self,
        job_id: uuid.UUID,
        user_id: uuid.UUID,
        file_sha256: str,
        file_name: str,
        storage_key: str,
        mode: str,
        dry_run_id: Optional[uuid.UUID],
    ) -> None:
        try:
            async with unit_of_work(self.db):
                await self.crud.acquire_lock()
                await self._purge_expired()
                await self.crud.fail_stale(_now() - STALE_AFTER)
                if await self.crud.active_id() is not None:
                    raise ConflictError("A Cin7 import is already running")
                email = await self.db.scalar(select(User.email).where(User.id == user_id))
                if email is None:
                    raise NotFoundError("User not found")
                self.crud.add(
                    Cin7ImportRun(
                        id=job_id,
                        user_id=user_id,
                        user_email=str(email),
                        file_sha256=file_sha256,
                        file_name=file_name,
                        storage_key=storage_key,
                        mode=mode,
                        status="queued",
                        dry_run_id=dry_run_id,
                        summary={},
                        warnings=[],
                        errors=[],
                        warning_count=0,
                        error_count=0,
                        barcode_replacements=[],
                        active_lock=True,
                    )
                )
                await self.db.flush()
        except IntegrityError as exc:
            raise ConflictError("A Cin7 import is already running") from exc

    async def _finish(self, job_id: uuid.UUID) -> None:
        async with unit_of_work(self.db):
            await self.crud.acquire_lock()
            job = await self.crud.get(job_id)
            if job is None or job.status != "running":
                return
            storage_key = job.storage_key
            job_id = job.id
            outcome = await self._import(job)
            drop_storage = bool(outcome.pop("drop_storage", False))
            await self.crud.mark(job_id, outcome)
            if drop_storage and storage_key:
                await self._drop_storage(storage_key)

    async def _import(self, job: Cin7ImportRun) -> dict[str, object]:
        storage_key = job.storage_key
        mode = job.mode
        file_sha256 = job.file_sha256
        dry_run_id = job.dry_run_id
        if not storage_key:
            return self._failed([{"message": "Upload expired. Run the dry run again."}])
        nested = await self.db.begin_nested()
        try:
            if mode == "commit":
                await self._recheck_commit(dry_run_id, file_sha256)
            data = await asyncio.to_thread(read_bytes, storage_key)
            with tempfile.TemporaryDirectory(prefix="cin7-import-") as tmp:
                root = Path(tmp)
                extract_zip(data, root)
                export_dir = locate_export_dir(root)
                report = await run_import(self.db, export_dir)
                if find_file(export_dir, "InventoryList", ".csv") is None:
                    report.errors.append({"message": "InventoryList file not found"})
            keep = mode == "commit" and not report.errors
            if keep:
                await self._recheck_commit(dry_run_id, file_sha256)
                await nested.commit()
            else:
                await nested.rollback()
                self.db.expunge_all()
            return self._from_report(report, mode, keep)
        except Exception as exc:
            await nested.rollback()
            self.db.expunge_all()
            logger.warning("cin7 import job %s failed", job.id)
            return self._failed([{"message": _safe_message(exc)}])

    def _from_report(self, report: ImportReport, mode: str, kept: bool) -> dict[str, object]:
        errors = list(report.errors)
        failed = bool(errors) or (mode == "commit" and not kept)
        return {
            "status": "failed" if failed else "completed",
            "finished_at": _now(),
            "summary": _summary(report),
            "warnings": list(report.warnings[:MAX_STORED_MESSAGES]),
            "errors": errors[:MAX_STORED_MESSAGES],
            "warning_count": len(report.warnings),
            "error_count": len(errors),
            "barcode_replacements": list(report.barcode_replacements),
            "drop_storage": bool(kept),
        }

    def _failed(self, errors: list[dict[str, str]]) -> dict[str, object]:
        return {
            "status": "failed",
            "finished_at": _now(),
            "summary": {
                "entities": {},
                "price_changes": {},
                "generated_barcodes": 0,
                "generated_barcodes_blank": 0,
                "generated_barcodes_shared": 0,
            },
            "warnings": [],
            "errors": errors,
            "warning_count": 0,
            "error_count": len(errors),
            "barcode_replacements": [],
            "drop_storage": False,
        }

    async def _recheck_commit(self, dry_run_id: Optional[uuid.UUID], file_sha256: str) -> None:
        if dry_run_id is None:
            raise ConflictError("Commit requires a completed dry run")
        dry = await self.crud.get(dry_run_id)
        if dry is None:
            raise NotFoundError("Cin7 import not found")
        await self._reject_unless_committable(dry, file_sha256)

    async def _reject_unless_committable(self, dry: Cin7ImportRun, file_sha256: str) -> None:
        if dry.mode != "dry_run" or dry.status != "completed":
            raise ConflictError("Commit requires a completed dry run")
        if dry.file_sha256 != file_sha256.lower():
            raise ConflictError("File hash does not match the dry run")
        if dry.error_count != 0:
            raise ConflictError("Dry run had errors")
        if not dry.storage_key:
            raise ValidationError("Upload expired. Run the dry run again.")
        latest = await self.crud.latest_commit_finished_at()
        if latest is not None and dry.finished_at is not None and latest >= dry.finished_at:
            raise ConflictError("Cin7 data was imported after this dry run")

    async def _drop_storage(self, storage_key: str) -> None:
        await asyncio.to_thread(_delete_quiet, storage_key)
        await self.crud.clear_storage(storage_key)

    async def _purge_expired(self) -> None:
        cutoff = _now() - RETENTION
        expired = await self.crud.expired_uploads(cutoff)
        active = await self.db.scalars(
            select(Cin7ImportRun.storage_key).where(
                Cin7ImportRun.active_lock.is_(True),
                Cin7ImportRun.storage_key.is_not(None),
            )
        )
        in_use = {key for key in active.all() if key}
        freed: set[str] = set()
        for row in expired:
            key = row.storage_key
            if not key or key in in_use:
                continue
            if key not in freed:
                await asyncio.to_thread(_delete_quiet, key)
                freed.add(key)
            row.storage_key = None

    async def _read_upload(
        self,
        file: Optional[UploadFile],
        files: Optional[list[UploadFile]],
    ) -> tuple[bytes, str]:
        uploads = [item for item in [file, *(files or [])] if item is not None and item.filename]
        if not uploads:
            raise ValidationError("Choose a Cin7 export zip or the export files")
        if len(uploads) == 1 and uploads[0].filename.lower().endswith(".zip"):
            data = await self._read_limited(uploads[0])
            validate_zip(data)
            return data, Path(uploads[0].filename).name
        named: list[tuple[str, bytes]] = []
        for item in uploads:
            payload = await self._read_limited(item)
            named.append((Path(item.filename).name, payload))
        data = pack_export_files(named)
        return data, "cin7-export.zip"

    async def _read_limited(self, upload: UploadFile) -> bytes:
        from app.services.cin7_import.archive import MAX_UPLOAD_BYTES

        chunks: list[bytes] = []
        total = 0
        while True:
            block = await upload.read(_READ_CHUNK)
            if not block:
                break
            total += len(block)
            if total > MAX_UPLOAD_BYTES:
                raise ValidationError("File exceeds the 100 MB upload limit")
            chunks.append(block)
        if total == 0:
            raise ValidationError("Upload is empty")
        return b"".join(chunks)
