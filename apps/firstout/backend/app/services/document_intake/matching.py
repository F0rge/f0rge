"""Match an extracted supplier document to suppliers and SKUs."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from decimal import Decimal
from difflib import SequenceMatcher
from typing import Optional

from app.schemas.document_intake import (
    ExtractedDocument,
    ExtractedLine,
    ReviewFlag,
    SkuMatchOut,
    SupplierMatchOut,
)
from app.services.document_intake.pricing import (
    CENT,
    extended,
    money,
    net_unit_price,
    whole_qty,
    within_cent,
)
from app.services.suppliers import normalize_vat_number

_CODE_CONFIDENCE = 1.0
_SUPPLIER_REF_CONFIDENCE = 0.98
_BARCODE_CONFIDENCE = 0.95
_OUR_REF_CONFIDENCE = 0.95
_LOW_CONFIDENCE = 0.9
_FUZZY_FLOOR = 0.72


@dataclass
class SupplierRecord:
    id: uuid.UUID
    name: str
    vat_number: Optional[str]
    address: Optional[str]


@dataclass
class SkuRecord:
    id: uuid.UUID
    our_ref: str
    our_barcode: str
    name: str
    design: str
    fabric: str
    supplier_ref: Optional[str]


@dataclass
class PriceRecord:
    sku_id: uuid.UUID
    supplier_id: uuid.UUID
    supplier_sku: Optional[str]


def _norm(value: Optional[str]) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip().lower()


def _code(value: Optional[str]) -> str:
    if not value:
        return ""
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _ratio(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, left, right).ratio()


def _fuzzy_confidence(ratio: float) -> float:
    if ratio >= 0.99:
        return 0.88
    if ratio >= 0.86:
        return 0.8
    return 0.74


def match_supplier(
    name: str,
    vat_number: Optional[str],
    address: Optional[str],
    suppliers: list[SupplierRecord],
) -> tuple[SupplierMatchOut, list[SupplierMatchOut]]:
    extracted_vat = normalize_vat_number(vat_number)
    extracted_name = name.strip() or "Unknown supplier"

    if extracted_vat:
        vat_hits = [
            row for row in suppliers if normalize_vat_number(row.vat_number) == extracted_vat
        ]
        if len(vat_hits) == 1:
            row = vat_hits[0]
            chosen = SupplierMatchOut(
                supplier_id=row.id,
                name=row.name,
                vat_number=row.vat_number,
                address=row.address,
                confidence=1.0,
                reason=f"VAT number matches {row.name}.",
            )
            return chosen, [chosen]
        if len(vat_hits) > 1:
            many = [
                SupplierMatchOut(
                    supplier_id=row.id,
                    name=row.name,
                    vat_number=row.vat_number,
                    address=row.address,
                    confidence=0.7,
                    reason="More than one supplier has this VAT number. Pick the right one.",
                )
                for row in vat_hits
            ]
            return many[0], many

    name_key = _norm(extracted_name)
    for row in suppliers:
        if name_key and _norm(row.name) == name_key:
            chosen = SupplierMatchOut(
                supplier_id=row.id,
                name=row.name,
                vat_number=row.vat_number,
                address=row.address,
                confidence=0.98,
                reason="Supplier name matches.",
            )
            return chosen, [chosen]

    best: Optional[tuple[float, SupplierRecord]] = None
    for row in suppliers:
        ratio = _ratio(name_key, _norm(row.name))
        if ratio < 0.88:
            continue
        if best is None or ratio > best[0]:
            best = (ratio, row)
    if best is not None:
        ratio, row = best
        chosen = SupplierMatchOut(
            supplier_id=row.id,
            name=row.name,
            vat_number=row.vat_number,
            address=row.address,
            confidence=round(min(0.9, ratio), 2),
            reason=f"Supplier name is similar to {row.name}. Check it before saving.",
        )
        return chosen, [chosen]

    none = SupplierMatchOut(
        supplier_id=None,
        name=extracted_name,
        vat_number=extracted_vat,
        address=(address or "").strip() or None,
        confidence=0.0,
        reason="No existing supplier matches this name or VAT number. You can create a new supplier.",
    )
    return none, []


def match_sku_line(
    line: ExtractedLine,
    skus: list[SkuRecord],
    prices: list[PriceRecord],
    supplier_id: Optional[uuid.UUID],
) -> tuple[Optional[SkuMatchOut], list[SkuMatchOut]]:
    by_id = {row.id: row for row in skus}
    found: list[SkuMatchOut] = []
    code = _code(line.supplier_code)

    if code and supplier_id is not None:
        for price in prices:
            if price.supplier_id != supplier_id:
                continue
            if _code(price.supplier_sku) != code:
                continue
            sku = by_id.get(price.sku_id)
            if sku is None:
                continue
            found.append(
                SkuMatchOut(
                    sku_id=sku.id,
                    our_ref=sku.our_ref,
                    name=sku.name,
                    confidence=_CODE_CONFIDENCE,
                    reason=f"Supplier product code matches {sku.our_ref}.",
                )
            )

    if code:
        for sku in skus:
            if _code(sku.supplier_ref) == code:
                found.append(
                    SkuMatchOut(
                        sku_id=sku.id,
                        our_ref=sku.our_ref,
                        name=sku.name,
                        confidence=_SUPPLIER_REF_CONFIDENCE,
                        reason=f"Supplier ref on the SKU matches {sku.our_ref}.",
                    )
                )
            elif _code(sku.our_barcode) == code:
                found.append(
                    SkuMatchOut(
                        sku_id=sku.id,
                        our_ref=sku.our_ref,
                        name=sku.name,
                        confidence=_BARCODE_CONFIDENCE,
                        reason=f"Barcode matches {sku.our_ref}.",
                    )
                )
            elif _code(sku.our_ref) == code:
                found.append(
                    SkuMatchOut(
                        sku_id=sku.id,
                        our_ref=sku.our_ref,
                        name=sku.name,
                        confidence=_OUR_REF_CONFIDENCE,
                        reason=f"Our code matches {sku.our_ref}.",
                    )
                )

    description = _norm(line.description)
    if len(description) >= 4:
        for sku in skus:
            haystacks = [
                _norm(sku.name),
                _norm(sku.design),
                _norm(f"{sku.design} {sku.fabric}"),
            ]
            ratio = max(_ratio(description, item) for item in haystacks)
            if ratio < _FUZZY_FLOOR:
                continue
            found.append(
                SkuMatchOut(
                    sku_id=sku.id,
                    our_ref=sku.our_ref,
                    name=sku.name,
                    confidence=_fuzzy_confidence(ratio),
                    reason=f"Description is similar to {sku.name}.",
                )
            )

    if not found:
        return None, []

    # One row per SKU, keeping the strongest reason.
    best_by_sku: dict[uuid.UUID, SkuMatchOut] = {}
    for item in found:
        current = best_by_sku.get(item.sku_id)
        if current is None or item.confidence > current.confidence:
            best_by_sku[item.sku_id] = item
    ranked = sorted(best_by_sku.values(), key=lambda item: item.confidence, reverse=True)
    top = ranked[0]
    if len(ranked) > 1 and ranked[0].confidence == ranked[1].confidence and top.confidence >= 0.95:
        ambiguous = top.model_copy(
            update={
                "confidence": 0.6,
                "reason": "More than one SKU matches this code. Pick the right one.",
            }
        )
        return ambiguous, ranked[:3]
    alternatives = [item for item in ranked[1:4] if item.confidence >= _FUZZY_FLOOR]
    if top.confidence < _FUZZY_FLOOR:
        return None, alternatives
    return top, alternatives


def line_flags(index: int, line: ExtractedLine, match: Optional[SkuMatchOut]) -> list[ReviewFlag]:
    flags: list[ReviewFlag] = []
    label = f"Line {index}"
    qty_int = whole_qty(line.qty)
    if qty_int is None:
        flags.append(
            ReviewFlag(
                code="qty_not_whole",
                message=f"{label}: quantity {line.qty} is not a whole number. Purchase orders need whole units.",
            )
        )
    net = net_unit_price(
        line.unit_price, line.qty or Decimal("1"), line.discount_percent, line.discount_amount
    )
    if net <= 0:
        flags.append(
            ReviewFlag(
                code="price_not_positive",
                message=f"{label}: the price after discount is not above zero.",
            )
        )
    if line.vat_rate is not None and line.vat_amount is not None and line.qty > 0:
        expected_vat = extended(net, line.qty) * line.vat_rate
        if not within_cent(expected_vat, line.vat_amount):
            flags.append(
                ReviewFlag(
                    code="vat_inconsistent",
                    message=(
                        f"{label}: VAT is {money(line.vat_amount, CENT)} but {line.vat_rate} of the "
                        f"line comes to {money(expected_vat, CENT)}."
                    ),
                )
            )
    if line.line_total is not None and line.qty > 0:
        ex_vat = extended(net, line.qty)
        vat = line.vat_amount or Decimal("0")
        inc_vat = money(ex_vat + vat, CENT)
        if not within_cent(line.line_total, ex_vat) and not within_cent(line.line_total, inc_vat):
            flags.append(
                ReviewFlag(
                    code="line_total_mismatch",
                    message=(
                        f"{label}: the document line total {money(line.line_total, CENT)} "
                        f"does not match quantity times price ({ex_vat})."
                    ),
                )
            )
    if match is None:
        flags.append(
            ReviewFlag(
                code="unmatched_sku",
                message=f"{label}: no SKU match. Create a new SKU, link one, or skip this line.",
            )
        )
    elif match.confidence < _LOW_CONFIDENCE:
        flags.append(
            ReviewFlag(
                code="low_confidence",
                message=(
                    f"{label}: match to {match.our_ref} is only {int(match.confidence * 100)}% confident. "
                    f"{match.reason}"
                ),
            )
        )
    return flags


def document_flags(
    extracted: ExtractedDocument,
    computed_ex_vat: Decimal,
    duplicate: bool,
) -> list[ReviewFlag]:
    flags: list[ReviewFlag] = []
    charges = sum((row.amount for row in extracted.charges), Decimal("0"))
    vat = extracted.vat_total or Decimal("0")
    computed_with_vat = money(computed_ex_vat + charges + vat, CENT)
    computed_ex = money(computed_ex_vat + charges, CENT)
    if extracted.total is None:
        flags.append(
            ReviewFlag(
                code="total_missing",
                message="The document total was not read. Check the figures before saving.",
            )
        )
    elif not within_cent(extracted.total, computed_with_vat) and not within_cent(
        extracted.total, computed_ex
    ):
        flags.append(
            ReviewFlag(
                code="totals_mismatch",
                message=(
                    f"Totals do not add up: lines, VAT and charges come to {computed_with_vat} "
                    f"but the document says {money(extracted.total, CENT)}."
                ),
            )
        )
    rates = {row.vat_rate for row in extracted.lines if row.vat_rate is not None}
    if len(rates) > 1:
        flags.append(
            ReviewFlag(
                code="vat_inconsistent",
                message="Lines use more than one VAT rate. Check each line.",
            )
        )
    if duplicate:
        flags.append(
            ReviewFlag(
                code="duplicate_proforma",
                message="This proforma number is already filed for this supplier.",
            )
        )
    if not extracted.document_number.strip():
        flags.append(
            ReviewFlag(
                code="number_missing",
                message="The proforma number was not read. Type it in before saving.",
            )
        )
    if extracted.document_date is None:
        flags.append(
            ReviewFlag(
                code="date_missing",
                message="The document date was not read. Type it in before saving.",
            )
        )
    if not extracted.lines:
        flags.append(
            ReviewFlag(
                code="no_lines",
                message="No line items were read from this document.",
            )
        )
    return flags
