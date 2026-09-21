"""Effective Nia cap math (no_db)."""

from __future__ import annotations

from pathlib import Path

from types import SimpleNamespace

import pytest

from app.services.nia_caps import effective_nia_cap

pytestmark = pytest.mark.no_db


def test_effective_cap_inherits_team_default() -> None:
    user = SimpleNamespace(nia_monthly_token_cap=None)
    team = SimpleNamespace(nia_monthly_token_cap=5_000_000)
    assert effective_nia_cap(user, team) == 5_000_000


def test_effective_cap_uses_user_override() -> None:
    user = SimpleNamespace(nia_monthly_token_cap=1_000_000)
    team = SimpleNamespace(nia_monthly_token_cap=500_000)
    assert effective_nia_cap(user, team) == 1_000_000


def test_effective_cap_zero_override_blocks() -> None:
    user = SimpleNamespace(nia_monthly_token_cap=0)
    team = SimpleNamespace(nia_monthly_token_cap=500_000)
    assert effective_nia_cap(user, team) == 0


def test_remaining_matches_override_math() -> None:
    used = 539_343
    cap = effective_nia_cap(
        SimpleNamespace(nia_monthly_token_cap=1_000_000),
        SimpleNamespace(nia_monthly_token_cap=500_000),
    )
    remaining = max(cap - used, 0)
    assert remaining == 460_657


def test_update_paths_use_unit_of_work() -> None:
    """Writes must commit via unit_of_work — get_db rolls back otherwise."""
    settings_src = Path(__file__).resolve().parents[1] / "app/services/settings.py"
    caps_src = Path(__file__).resolve().parents[1] / "app/services/nia_caps.py"
    settings_text = settings_src.read_text()
    caps_text = caps_src.read_text()
    assert "unit_of_work" in settings_text
    assert "unit_of_work" in caps_text
    assert "async with unit_of_work(self.db):" in settings_text
    assert "async with unit_of_work(self.db):" in caps_text
