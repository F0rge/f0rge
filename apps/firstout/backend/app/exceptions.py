from __future__ import annotations

from f0rge_core.exceptions import ConflictError, DomainError


class ForbiddenError(DomainError):
    """Caller lacks a required permission. Mapped to HTTP 403."""


class DocumentLlmUnconfiguredError(DomainError):
    """OpenRouter key missing for supplier-document reading. HTTP 503."""

    def __init__(self) -> None:
        super().__init__("document_llm_unconfigured")


class CommsEncryptionUnconfiguredError(DomainError):
    """SETTINGS_ENCRYPTION_KEY missing or invalid. Mapped to HTTP 503."""

    def __init__(self) -> None:
        super().__init__("comms_encryption_unconfigured")


class CommsSmtpUnconfiguredError(DomainError):
    """SMTP mailbox not saved. Mapped to HTTP 503."""

    def __init__(self) -> None:
        super().__init__("comms_smtp_unconfigured")


class KitRequiresPickError(ConflictError):
    """Till kit is not fully at the showroom and has no matching pick. HTTP 409."""

    def __init__(self, kits: list[dict]) -> None:
        self.kits = kits
        message = " ".join(str(kit["message"]) for kit in kits if kit.get("message"))
        super().__init__(message or "Kit requires pick")
        self.payload = {
            "code": "kit_requires_pick",
            "message": self.detail,
            "kits": kits,
        }


class CommsSmtpFailedError(DomainError):
    """SMTP provider rejected the send. Mapped to HTTP 502."""

    def __init__(self, message: str) -> None:
        super().__init__("comms_smtp_failed")
        self.message = message
