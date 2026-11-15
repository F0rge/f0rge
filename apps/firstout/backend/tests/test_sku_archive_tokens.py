"""The supported bulk size fits its signed dependency snapshot request contract."""

from __future__ import annotations

import json
import uuid

import pytest
from pydantic import ValidationError

from app.schemas.record_workspace import WorkspaceExecute
from app.services.record_workspace_tokens import issue_token, read_token
from f0rge_db.organisation import tenant_id_ctx

pytestmark = pytest.mark.no_db


def test_five_hundred_sku_dependency_snapshots_round_trip_through_execute_contract():
    actor = uuid.uuid4()
    ids = [str(uuid.uuid4()) for _ in range(500)]
    revisions = {key: "a" * 64 for key in ids}
    dependencies = {key: "b" * 64 for key in ids}
    context = tenant_id_ctx.set(uuid.uuid4())
    try:
        token = issue_token(
            "preflight",
            "skus",
            actor,
            {
                "action": "archive",
                "patch": {},
                "ids": ids,
                "revisions": revisions,
                "dependencies": dependencies,
            },
        )
        assert 131072 < len(token) <= 262144
        body = WorkspaceExecute.model_validate_json(
            json.dumps({"preflight_token": token, "request_id": str(uuid.uuid4())})
        )
        claims = read_token(body.preflight_token, "preflight", "skus", actor)
        assert claims["ids"] == ids
        assert claims["revisions"] == revisions
        assert claims["dependencies"] == dependencies
        with pytest.raises(ValidationError):
            WorkspaceExecute(preflight_token="x" * 262145, request_id=uuid.uuid4())
    finally:
        tenant_id_ctx.reset(context)
