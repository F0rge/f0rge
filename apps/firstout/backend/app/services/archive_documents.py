from __future__ import annotations

from f0rge_core.exceptions import ConflictError


def assert_operational_document(document: object) -> None:
    if getattr(document, "is_archive", False):
        raise ConflictError("Imported historical documents are read-only")


def bill_display_number(bill) -> str:
    return bill.supplier_ref if bill.is_archive and bill.supplier_ref else bill.bill_number


def source_document_flags(document) -> dict[str, bool]:
    payload = getattr(document, "cin7_source_payload", None) or {}
    facts = payload.get("facts", {})
    return {
        "is_archive": bool(document.is_archive),
        "source_amounts_known": facts.get("amounts_known", True),
        "source_currency_known": facts.get("currency_known", True),
    }
