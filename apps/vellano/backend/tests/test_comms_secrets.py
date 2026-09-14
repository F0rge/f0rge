"""Fernet helpers for comms secrets. No database."""

from __future__ import annotations

import pytest
from cryptography.fernet import Fernet

from app.config import settings
from app.exceptions import CommsEncryptionUnconfiguredError
from app.services.comms.secrets import decrypt, encrypt

pytestmark = pytest.mark.no_db


def test_encrypt_decrypt_round_trip(monkeypatch: pytest.MonkeyPatch) -> None:
    key = Fernet.generate_key().decode()
    monkeypatch.setattr(settings, "settings_encryption_key", key)
    plaintext = "smtp-app-password"
    token = encrypt(plaintext)
    assert decrypt(token) == plaintext
    assert b"smtp-app-password" not in token


def test_missing_key_raises_unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "settings_encryption_key", "")
    with pytest.raises(CommsEncryptionUnconfiguredError) as exc:
        encrypt("secret")
    assert exc.value.detail == "comms_encryption_unconfigured"


def test_invalid_key_raises_unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "settings_encryption_key", "not-a-fernet-key")
    with pytest.raises(CommsEncryptionUnconfiguredError) as exc:
        encrypt("secret")
    assert exc.value.detail == "comms_encryption_unconfigured"
