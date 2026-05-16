from __future__ import annotations

import pytest
from cryptography.fernet import Fernet


def _with_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch settings to have a valid Fernet key."""
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("SETTINGS_ENCRYPTION_KEY", key)
    # Re-import so the patched env is picked up via settings reload.
    import importlib
    import app.config as cfg_mod
    import app.services.llm.encryption as enc_mod

    monkeypatch.setattr(cfg_mod.settings, "settings_encryption_key", key)
    # Force re-read of settings inside the module (it imports at top level).
    importlib.reload(enc_mod)


@pytest.fixture(autouse=True)
def patch_settings_key(monkeypatch: pytest.MonkeyPatch) -> None:
    _with_key(monkeypatch)


def test_encrypt_decrypt_roundtrip() -> None:
    from app.services.llm.encryption import decrypt, encrypt

    original = "sk-or-v1-supersecret"
    ciphertext = encrypt(original)
    assert isinstance(ciphertext, bytes)
    assert ciphertext != original.encode()
    recovered = decrypt(ciphertext)
    assert recovered == original


def test_decrypt_encrypt_roundtrip() -> None:
    from app.services.llm.encryption import decrypt, encrypt

    original = "another-secret-key-1234"
    assert decrypt(encrypt(original)) == original


def test_encrypt_returns_different_ciphertext_each_call() -> None:
    # Fernet uses a random IV so two encryptions of the same plaintext differ.
    from app.services.llm.encryption import encrypt

    ct1 = encrypt("same")
    ct2 = encrypt("same")
    assert ct1 != ct2


def test_empty_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    import importlib
    import app.config as cfg_mod
    import app.services.llm.encryption as enc_mod

    monkeypatch.setattr(cfg_mod.settings, "settings_encryption_key", "")
    importlib.reload(enc_mod)

    from app.services.llm.encryption import encrypt, decrypt

    with pytest.raises(ValueError, match="settings_encryption_key"):
        encrypt("anything")

    with pytest.raises(ValueError, match="settings_encryption_key"):
        decrypt(b"anything")
