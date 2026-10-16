"""Boot fixtures stay off unless SEED_BOOT_FIXTURES is set."""

from __future__ import annotations

import pytest

from app.config import settings
from app.main import seed_boot_fixtures
from app.services.role_user_seed import RoleUserSeedService
from app.services.storefront_system_actor import StorefrontSystemActorService
from app.services.till_seed import TillSeedService


@pytest.mark.no_db
async def test_boot_fixtures_default_off(monkeypatch: pytest.MonkeyPatch) -> None:
    assert settings.seed_boot_fixtures is False
    called: list[str] = []

    async def role_seed(self: RoleUserSeedService) -> None:
        called.append("roles")

    async def actor(self: StorefrontSystemActorService, company_id: object = None) -> None:
        called.append("actor")

    async def walk_in(self: TillSeedService) -> None:
        called.append("walk-in")

    monkeypatch.setattr(RoleUserSeedService, "seed", role_seed)
    monkeypatch.setattr(StorefrontSystemActorService, "ensure", actor)
    monkeypatch.setattr(TillSeedService, "seed_if_empty", walk_in)
    monkeypatch.setattr(settings, "seed_boot_fixtures", False)

    await seed_boot_fixtures(None)  # type: ignore[arg-type]

    assert called == []


@pytest.mark.no_db
async def test_boot_fixtures_when_enabled_calls_each_seed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called: list[str] = []

    async def role_seed(self: RoleUserSeedService) -> None:
        called.append("roles")

    async def actor(self: StorefrontSystemActorService, company_id: object = None) -> None:
        called.append("actor")

    async def walk_in(self: TillSeedService) -> None:
        called.append("walk-in")

    monkeypatch.setattr(RoleUserSeedService, "seed", role_seed)
    monkeypatch.setattr(StorefrontSystemActorService, "ensure", actor)
    monkeypatch.setattr(TillSeedService, "seed_if_empty", walk_in)
    monkeypatch.setattr(settings, "seed_boot_fixtures", True)

    await seed_boot_fixtures(None)  # type: ignore[arg-type]

    assert called == ["roles", "actor", "walk-in"]
