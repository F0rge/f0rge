"""Nia system-prompt composition (no_db)."""

from __future__ import annotations

import pytest

from app.nia.agent import NIA_INSTRUCTIONS

pytestmark = pytest.mark.no_db


def test_instructions_ban_emojis() -> None:
    assert "Never use emojis" in NIA_INSTRUCTIONS
    assert "headers, bullets, labels" in NIA_INSTRUCTIONS
    lower = NIA_INSTRUCTIONS.lower()
    assert "emoji" in lower
    assert "plain words" in lower
