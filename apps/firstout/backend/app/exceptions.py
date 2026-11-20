from __future__ import annotations

from f0rge_core.exceptions import ConflictError, DomainError


class ForbiddenError(DomainError):
    """Caller lacks a required permission. Mapped to HTTP 403."""


class RecordWorkspaceUnconfiguredError(DomainError):
    """Bulk snapshots require an operator-configured durable signing key. HTTP 503."""

    def __init__(self) -> None:
        super().__init__(
            "Bulk actions are unavailable. Configure RECORD_WORKSPACE_SIGNING_KEY "
            "with at least 32 characters on the API, then review the selection again."
        )


class McpTokensUnconfiguredError(DomainError):
    def __init__(self) -> None:
        super().__init__("Personal MCP tokens are temporarily unavailable")


class DocumentLlmUnconfiguredError(DomainError):
    """OpenRouter key missing for supplier-document reading. HTTP 503."""

    def __init__(self) -> None:
        super().__init__("document_llm_unconfigured")


class TillPriceConflictError(ConflictError):
    """The prices on the till need to be reviewed before the sale can continue."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.payload = {"code": "till_price_conflict", "message": detail}


class HeldResumeTargetChangedError(ConflictError):
    """The selected held basket was edited or consumed before this resume."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.payload = {"code": "held_resume_target_changed", "message": detail}


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


class RateLimitedError(DomainError):
    """Too many attempts from this email or IP. Mapped to HTTP 429."""

    def __init__(self, detail: str = "Too many attempts. Try again later.") -> None:
        super().__init__(detail)


class TillBasketConflictError(ConflictError):
    """The server basket moved on; the payload carries the current basket."""

    def __init__(self, code: str, detail: str, basket: dict | None = None, **extra: object) -> None:
        super().__init__(detail)
        self.payload = {"code": code, "message": detail, **extra, "basket": basket}


class HeldSaleExpiredError(HeldResumeTargetChangedError):
    """The held sale outlived the hold time; it is gone and its stock released."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.payload = {"code": "held_sale_expired", "message": detail}
