from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends

from app.dependencies.auth import get_current_user_id
from app.dependencies.record_workspace import (
    get_record_workspace_execute_service,
    get_record_workspace_service,
)
from app.schemas.record_workspace import (
    WorkspaceExecute,
    WorkspaceExecuteResponse,
    WorkspacePreflight,
    WorkspacePreflightResponse,
    WorkspaceQuery,
    WorkspaceQueryResponse,
    WorkspaceResource,
)
from app.services.record_workspace import RecordWorkspaceService
from app.services.record_workspace_execute import RecordWorkspaceExecuteService

record_workspace_router = APIRouter(prefix="/api/v1/record-workspaces", tags=["record-workspaces"])


@record_workspace_router.post("/{resource}/query", response_model=WorkspaceQueryResponse)
async def query_records(
    resource: WorkspaceResource,
    body: WorkspaceQuery,
    actor: uuid.UUID = Depends(get_current_user_id),
    service: RecordWorkspaceService = Depends(get_record_workspace_service),
):
    return await service.query(resource, body, actor)


@record_workspace_router.post("/{resource}/preflight", response_model=WorkspacePreflightResponse)
async def preflight_records(
    resource: WorkspaceResource,
    body: WorkspacePreflight,
    actor: uuid.UUID = Depends(get_current_user_id),
    service: RecordWorkspaceService = Depends(get_record_workspace_service),
):
    return await service.preflight(resource, body, actor)


@record_workspace_router.post("/{resource}/execute", response_model=WorkspaceExecuteResponse)
async def execute_records(
    resource: WorkspaceResource,
    body: WorkspaceExecute,
    actor: uuid.UUID = Depends(get_current_user_id),
    service: RecordWorkspaceExecuteService = Depends(get_record_workspace_execute_service),
):
    return await service.execute(resource, body, actor)
