"""Role-DDL configuration remains an explicit choice for both migration directions."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Optional
from unittest.mock import Mock

import pytest


@pytest.fixture(
    params=[
        (
            "004_external_readonly_role.py",
            "d4e7a1b2c903",
            "c9f82b4d1e73",
            "healthtracker_ro",
            "HEALTHTRACKER_RO_PASSWORD",
        ),
        (
            "019_app_role.py",
            "e8f1a2b3c4d5",
            "018",
            "healthtracker_app",
            "HEALTHTRACKER_APP_PASSWORD",
        ),
    ],
    ids=["readonly-role", "app-role"],
)
def role_migration(request: pytest.FixtureRequest) -> tuple[ModuleType, str, str]:
    filename, revision, down_revision, role, password_env = request.param
    path = Path(__file__).parents[1] / "migrations" / "versions" / filename
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert migration.revision == revision
    assert migration.down_revision == down_revision
    return migration, role, password_env


@pytest.mark.parametrize("direction", ["upgrade", "downgrade"])
@pytest.mark.parametrize("value", ["1", "true", "yes", "TRUE", "Yes"])
def test_skip_role_ddl_never_opens_database_or_requires_password(
    role_migration: tuple[ModuleType, str, str],
    direction: str,
    value: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration, _role, password_env = role_migration
    monkeypatch.setenv("SKIP_DATABASE_ROLE_DDL", value)
    monkeypatch.delenv(password_env, raising=False)
    get_bind = Mock(side_effect=AssertionError("Skipped role DDL must not access the database"))
    monkeypatch.setattr(migration, "op", SimpleNamespace(get_bind=get_bind))

    getattr(migration, direction)()

    get_bind.assert_not_called()


@pytest.mark.parametrize("direction", ["upgrade", "downgrade"])
@pytest.mark.parametrize("value", [None, "", "0", "false", "no", " true ", "YES "])
def test_unset_or_false_skip_flag_keeps_role_ddl(
    role_migration: tuple[ModuleType, str, str],
    direction: str,
    value: Optional[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration, role, password_env = role_migration
    if value is None:
        monkeypatch.delenv("SKIP_DATABASE_ROLE_DDL", raising=False)
    else:
        monkeypatch.setenv("SKIP_DATABASE_ROLE_DDL", value)
    monkeypatch.setenv(password_env, "synthetic-migration-password")
    bind = Mock()
    monkeypatch.setattr(migration, "op", SimpleNamespace(get_bind=lambda: bind))

    getattr(migration, direction)()

    statements = [str(call.args[0]) for call in bind.execute.call_args_list]
    expected = f"CREATE ROLE {role}" if direction == "upgrade" else f"DROP ROLE IF EXISTS {role}"
    assert any(expected in statement for statement in statements)


def test_upgrade_without_skip_still_requires_role_password(
    role_migration: tuple[ModuleType, str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    migration, _role, password_env = role_migration
    monkeypatch.delenv("SKIP_DATABASE_ROLE_DDL", raising=False)
    monkeypatch.delenv(password_env, raising=False)
    get_bind = Mock(side_effect=AssertionError("Missing password must stop before database access"))
    monkeypatch.setattr(migration, "op", SimpleNamespace(get_bind=get_bind))

    with pytest.raises(RuntimeError, match=password_env):
        migration.upgrade()

    get_bind.assert_not_called()
