"""Nia OpenRouter reasoning model_settings (effort + exclude)."""

from __future__ import annotations

import pytest

from app.config import settings
from app.nia.agent import build_nia_model_settings

pytestmark = pytest.mark.no_db


def test_defaults_effort_low_and_exclude(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "openrouter_reasoning_effort", "low")
    monkeypatch.setattr(settings, "openrouter_reasoning_exclude", True)
    ms = build_nia_model_settings()
    assert ms is not None
    reasoning = ms["openrouter_reasoning"]
    assert reasoning["effort"] == "low"
    assert reasoning["exclude"] is True
    assert reasoning["enabled"] is True


def test_effort_max_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "openrouter_reasoning_effort", "max")
    monkeypatch.setattr(settings, "openrouter_reasoning_exclude", True)
    ms = build_nia_model_settings()
    assert ms is not None
    assert ms["openrouter_reasoning"]["effort"] == "max"


def test_invalid_effort_falls_back_to_low(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "openrouter_reasoning_effort", "banana")
    monkeypatch.setattr(settings, "openrouter_reasoning_exclude", False)
    ms = build_nia_model_settings()
    assert ms is not None
    assert ms["openrouter_reasoning"]["effort"] == "low"
    assert ms["openrouter_reasoning"]["exclude"] is False


def test_empty_effort_and_exclude_false_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "openrouter_reasoning_effort", "")
    monkeypatch.setattr(settings, "openrouter_reasoning_exclude", False)
    assert build_nia_model_settings() is None


def test_exclude_alone_sets_exclude_without_effort(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "openrouter_reasoning_effort", "  ")
    monkeypatch.setattr(settings, "openrouter_reasoning_exclude", True)
    ms = build_nia_model_settings()
    assert ms is not None
    reasoning = ms["openrouter_reasoning"]
    assert "effort" not in reasoning
    assert reasoning["exclude"] is True
    assert reasoning["enabled"] is True
