from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Response, UploadFile

from app.dependencies.auth import get_cin7_import_job_service, require_owner
from app.schemas.cin7_import import Cin7ImportCommitRequest, Cin7ImportRunResponse
from app.services.cin7_import_jobs import Cin7ImportJobService

cin7_imports_router = APIRouter(prefix="/api/v1/cin7-imports", tags=["cin7-imports"])


@cin7_imports_router.get("", response_model=list[Cin7ImportRunResponse])
async def list_cin7_imports(
    _: uuid.UUID = Depends(require_owner),
    service: Cin7ImportJobService = Depends(get_cin7_import_job_service),
) -> list[Cin7ImportRunResponse]:
    return await service.list_runs()


@cin7_imports_router.post("", response_model=Cin7ImportRunResponse, status_code=202)
async def start_cin7_import(
    file: Optional[UploadFile] = File(None),
    files: Optional[list[UploadFile]] = File(None),
    user_id: uuid.UUID = Depends(require_owner),
    service: Cin7ImportJobService = Depends(get_cin7_import_job_service),
) -> Cin7ImportRunResponse:
    return await service.start_dry_run(file, files, user_id)


@cin7_imports_router.get("/{run_id}", response_model=Cin7ImportRunResponse)
async def get_cin7_import(
    run_id: uuid.UUID,
    _: uuid.UUID = Depends(require_owner),
    service: Cin7ImportJobService = Depends(get_cin7_import_job_service),
) -> Cin7ImportRunResponse:
    return await service.get_run(run_id)


@cin7_imports_router.get("/{run_id}/warnings.csv")
async def cin7_import_warnings_csv(
    run_id: uuid.UUID,
    _: uuid.UUID = Depends(require_owner),
    service: Cin7ImportJobService = Depends(get_cin7_import_job_service),
) -> Response:
    content = await service.warnings_csv(run_id)
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="cin7-import-warnings.csv"'},
    )


@cin7_imports_router.get("/{run_id}/barcodes.csv")
async def cin7_import_barcodes_csv(
    run_id: uuid.UUID,
    _: uuid.UUID = Depends(require_owner),
    service: Cin7ImportJobService = Depends(get_cin7_import_job_service),
) -> Response:
    content = await service.barcodes_csv(run_id)
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="cin7-import-barcodes.csv"'},
    )


@cin7_imports_router.get("/{run_id}/errors.csv")
async def cin7_import_errors_csv(
    run_id: uuid.UUID,
    _: uuid.UUID = Depends(require_owner),
    service: Cin7ImportJobService = Depends(get_cin7_import_job_service),
) -> Response:
    content = await service.errors_csv(run_id)
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="cin7-import-errors.csv"'},
    )


@cin7_imports_router.post("/{run_id}/commit", response_model=Cin7ImportRunResponse, status_code=202)
async def commit_cin7_import(
    run_id: uuid.UUID,
    body: Cin7ImportCommitRequest,
    user_id: uuid.UUID = Depends(require_owner),
    service: Cin7ImportJobService = Depends(get_cin7_import_job_service),
) -> Cin7ImportRunResponse:
    return await service.start_commit(run_id, body.file_sha256, user_id)
