from __future__ import annotations

import uuid

import pytest
from sqlalchemy.orm import Session

from f0rge_db.auth_context import user_id_ctx
from f0rge_db.organisation import (
    apply_tenant_context,
    clear_organisation_session,
    register_organisation_hook,
    tenant_id_ctx,
)


class RecordingConnection:
    def __init__(self):
        self.statements = []

    def execute(self, statement, params=None):
        self.statements.append((str(statement), params))


class RecordingSession:
    def __init__(self):
        self.info = {}
        self.calls = []

    async def execute(self, statement, params=None):
        self.calls.append((str(statement), params))

    async def rollback(self):
        self.calls.append("rollback")

    async def commit(self):
        self.calls.append("commit")


def test_hook_is_opt_in_transaction_local_and_leaves_marrow_context_unchanged():
    class OrganisationSession(Session):
        pass

    register_organisation_hook(OrganisationSession)
    register_organisation_hook(OrganisationSession)
    tenant, user = uuid.uuid4(), uuid.uuid4()
    tenant_token, user_token = tenant_id_ctx.set(tenant), user_id_ctx.set(user)
    try:
        conn = RecordingConnection()
        session = OrganisationSession()
        session.dispatch.after_begin(session, None, conn)
        assert conn.statements == [
            ("SELECT set_config('app.tenant_id', :tenant_id, true)", {"tenant_id": str(tenant)})
        ]
        assert user_id_ctx.get() == user
        ordinary = Session()
        other_conn = RecordingConnection()
        ordinary.dispatch.after_begin(ordinary, None, other_conn)
        assert not any("app.tenant_id" in statement for statement, _ in other_conn.statements)
    finally:
        tenant_id_ctx.reset(tenant_token)
        user_id_ctx.reset(user_token)


async def test_session_binding_rejects_switch_and_cleanup_resets_after_rollback():
    session = RecordingSession()
    tenant = uuid.uuid4()
    await apply_tenant_context(session, tenant)
    assert session.calls[-1] == (
        "SELECT set_config('app.tenant_id', :tenant_id, true)",
        {"tenant_id": str(tenant)},
    )
    with pytest.raises(Exception, match="Cannot switch tenant"):
        await apply_tenant_context(session, uuid.uuid4())
    await clear_organisation_session(session)
    assert session.calls[-3:] == ["rollback", ("RESET app.tenant_id", None), "commit"]
    assert not session.info
