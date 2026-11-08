from __future__ import annotations

import datetime
import uuid
from unittest.mock import AsyncMock

import pytest
from f0rge_core.exceptions import UnauthorizedError
from f0rge_db.organisation import tenant_id_ctx

from app.crud.password_reset_token import PasswordResetTokenCRUD
from app.crud.user import TeamCRUD, UserCRUD

pytestmark = pytest.mark.no_db


@pytest.mark.parametrize(
    "resource,method,args",
    [
        (UserCRUD, "list_all", ()),
        (UserCRUD, "count", ()),
        (UserCRUD, "get_by_id", (uuid.uuid4(),)),
        (UserCRUD, "get_by_email", ("staff@example.com",)),
        (UserCRUD, "list_till_with_null_default", ()),
        (UserCRUD, "add_and_flush", (object(),)),
        (UserCRUD, "save", ()),
        (TeamCRUD, "get_first", ()),
        (TeamCRUD, "get_by_id", (uuid.uuid4(),)),
        (TeamCRUD, "count", ()),
        (PasswordResetTokenCRUD, "invalidate_unused", (uuid.uuid4(), datetime.datetime.utcnow())),
        (PasswordResetTokenCRUD, "add_and_flush", (object(),)),
    ],
)
async def test_directory_crud_without_context_fails_before_database(resource, method, args):
    db = AsyncMock()
    token = tenant_id_ctx.set(None)
    try:
        with pytest.raises(UnauthorizedError, match="Tenant context required"):
            await getattr(resource(db), method)(*args)
        db.execute.assert_not_called()
        db.scalar.assert_not_called()
        db.scalars.assert_not_called()
        db.add.assert_not_called()
    finally:
        tenant_id_ctx.reset(token)


@pytest.mark.parametrize("resource,kind", [(UserCRUD, "user"), (TeamCRUD, "team")])
@pytest.mark.parametrize("method", ["add_and_flush", "delete", "refresh", "commit_refresh"])
async def test_directory_write_rejects_other_tenant_object(resource, kind, method):
    from app.models.team import Team
    from app.models.user import User

    db = AsyncMock()
    foreign_team = uuid.uuid4()
    obj = (
        Team(id=foreign_team, name="Other")
        if kind == "team"
        else User(
            id=uuid.uuid4(),
            team_id=foreign_team,
            email="other@example.com",
            password_hash="not-a-password",
            role="owner",
        )
    )
    token = tenant_id_ctx.set(uuid.uuid4())
    try:
        with pytest.raises(UnauthorizedError, match="outside tenant scope"):
            await getattr(resource(db), method)(obj)
        db.add.assert_not_called()
        db.delete.assert_not_called()
        db.refresh.assert_not_called()
    finally:
        tenant_id_ctx.reset(token)


async def test_storefront_actor_requires_matching_tenant_context():
    from app.services.storefront_system_actor import StorefrontSystemActorService
    from f0rge_core.exceptions import ValidationError

    db = AsyncMock()
    service = StorefrontSystemActorService(db)
    token = tenant_id_ctx.set(None)
    try:
        with pytest.raises(UnauthorizedError):
            await service.ensure()
        tenant_id_ctx.set(uuid.uuid4())
        with pytest.raises(ValidationError, match="does not match"):
            await service.ensure(uuid.uuid4())
        db.get.assert_not_called()
        db.scalar.assert_not_called()
    finally:
        tenant_id_ctx.reset(token)
