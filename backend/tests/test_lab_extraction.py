from __future__ import annotations

import json
from pathlib import Path
from typing import Any, List

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.exceptions import ValidationError
from app.schemas.lab_marker import CatalogHint
from app.services import lab_extraction as extraction_module
from app.services.lab_extraction import LabExtractionService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _valid_payload(
    *,
    canonical_match: str | None = "hemoglobin",
    proposed_canonical: str | None = None,
    value: float | None = 15.5,
    value_text: str | None = None,
    confidence: float = 0.92,
    lab_date: str = "2026-05-01",
) -> dict:
    marker: dict[str, Any] = {
        "canonical_match": canonical_match,
        "proposed_canonical": proposed_canonical,
        "display_name": "Hemoglobin",
        "value": value,
        "value_text": value_text,
        "unit": "g/dL",
        "ref_low": 13.7,
        "ref_high": 17.2,
        "ref_text": None,
    }
    return {
        "lab": {
            "lab_date": lab_date,
            "name": "Test Lab",
            "type": "blood",
            "lab_location": None,
            "notes": None,
        },
        "markers": [marker],
        "confidence": confidence,
    }


@pytest.fixture
def hints() -> List[CatalogHint]:
    return [
        CatalogHint(
            canonical="hemoglobin",
            display="Hemoglobin",
            aliases=["hb", "hemoglobina"],
            common_units=["g/dL"],
        ),
        CatalogHint(
            canonical="ferritin",
            display="Ferritin",
            aliases=[],
            common_units=["ug/L"],
        ),
    ]


@pytest.fixture(autouse=True)
def lab_extraction_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_resolve(db: AsyncSession) -> tuple[str, str]:
        return ("test-api-key", settings.openrouter_model)

    monkeypatch.setattr(
        "app.services.llm.factory.resolve_llm_credentials",
        _fake_resolve,
    )


@pytest.fixture
def extraction_service(async_db: AsyncSession) -> LabExtractionService:
    return LabExtractionService(async_db)


@pytest.fixture
def audit_log_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Redirect the audit log to tmp_path so we don't pollute the real file."""
    path = tmp_path / "extraction_audit.jsonl"
    monkeypatch.setattr(extraction_module, "_AUDIT_LOG_PATH", str(path))
    return path


def _patch_call(
    monkeypatch: pytest.MonkeyPatch,
    responses: List[str | Exception] | str,
    capture: List[List[dict]] | None = None,
) -> None:
    """Patch _call_openrouter with a queued list of responses.

    Accepts either a list (one response per call) or a single string (used once).
    If `capture` is supplied, each call appends the messages it received.
    """
    queue = list(responses) if isinstance(responses, list) else [responses]

    async def fake(messages: List[dict], model: str, api_key: str) -> str:
        if capture is not None:
            capture.append(messages)
        if not queue:
            raise AssertionError("fake _call_openrouter called more times than expected")
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(extraction_module, "_call_openrouter", fake)


# ---------------------------------------------------------------------------
# Happy-path: known marker → canonical_match
# ---------------------------------------------------------------------------


async def test_extract_text_known_marker_keeps_canonical_match(
    monkeypatch: pytest.MonkeyPatch,
    hints: List[CatalogHint],
    audit_log_path: Path,
    extraction_service: LabExtractionService,
) -> None:
    raw = json.dumps(_valid_payload(canonical_match="hemoglobin"))
    _patch_call(monkeypatch, [raw])

    result = await extraction_service.extract_text("doc", hints)

    assert result.attempts == 1
    assert result.retried_due_to == []
    assert len(result.payload.markers) == 1
    m = result.payload.markers[0]
    assert m.canonical_match == "hemoglobin"
    assert m.proposed_canonical is None
    assert m.value == 15.5


# ---------------------------------------------------------------------------
# Unknown marker → proposed_canonical preserved
# ---------------------------------------------------------------------------


async def test_extract_unknown_marker_preserves_proposed_canonical(
    monkeypatch: pytest.MonkeyPatch,
    hints: List[CatalogHint],
    audit_log_path: Path,
    extraction_service: LabExtractionService,
) -> None:
    raw = json.dumps(_valid_payload(canonical_match=None, proposed_canonical="brand_new_marker"))
    _patch_call(monkeypatch, [raw])

    result = await extraction_service.extract_text("doc", hints)
    m = result.payload.markers[0]
    assert m.canonical_match is None
    assert m.proposed_canonical == "brand_new_marker"


# ---------------------------------------------------------------------------
# Non-numeric value preserved verbatim
# ---------------------------------------------------------------------------


async def test_extract_non_numeric_value_preserved(
    monkeypatch: pytest.MonkeyPatch,
    hints: List[CatalogHint],
    audit_log_path: Path,
    extraction_service: LabExtractionService,
) -> None:
    raw = json.dumps(_valid_payload(value=None, value_text="POSITIVE"))
    _patch_call(monkeypatch, [raw])
    result = await extraction_service.extract_text("doc", hints)
    m = result.payload.markers[0]
    assert m.value is None
    assert m.value_text == "POSITIVE"


# ---------------------------------------------------------------------------
# Defensive JSON parsing
# ---------------------------------------------------------------------------


async def test_defensive_parsing_raw_json(
    monkeypatch: pytest.MonkeyPatch,
    hints: List[CatalogHint],
    audit_log_path: Path,
    extraction_service: LabExtractionService,
) -> None:
    raw = json.dumps(_valid_payload())
    _patch_call(monkeypatch, [raw])
    result = await extraction_service.extract_text("doc", hints)
    assert result.attempts == 1


async def test_defensive_parsing_fenced_json(
    monkeypatch: pytest.MonkeyPatch,
    hints: List[CatalogHint],
    audit_log_path: Path,
    extraction_service: LabExtractionService,
) -> None:
    raw = "```json\n" + json.dumps(_valid_payload()) + "\n```"
    _patch_call(monkeypatch, [raw])
    result = await extraction_service.extract_text("doc", hints)
    assert result.attempts == 1
    assert result.payload.markers[0].canonical_match == "hemoglobin"


async def test_defensive_parsing_first_brace_match(
    monkeypatch: pytest.MonkeyPatch,
    hints: List[CatalogHint],
    audit_log_path: Path,
    extraction_service: LabExtractionService,
) -> None:
    raw = "Here is your data: " + json.dumps(_valid_payload()) + " hope it helps!"
    _patch_call(monkeypatch, [raw])
    result = await extraction_service.extract_text("doc", hints)
    assert result.attempts == 1


# ---------------------------------------------------------------------------
# Schema rejection retry
# ---------------------------------------------------------------------------


async def test_schema_rejection_then_retry_success(
    monkeypatch: pytest.MonkeyPatch,
    hints: List[CatalogHint],
    audit_log_path: Path,
    extraction_service: LabExtractionService,
) -> None:
    # First response: confidence out of range (>1.0) → Pydantic rejects.
    bad = json.dumps(_valid_payload(confidence=1.7))
    good = json.dumps(_valid_payload(confidence=0.9))
    _patch_call(monkeypatch, [bad, good])

    result = await extraction_service.extract_text("doc", hints)
    assert result.attempts == 2
    assert len(result.retried_due_to) >= 1
    assert result.payload.confidence == 0.9


# ---------------------------------------------------------------------------
# Three-strike failure
# ---------------------------------------------------------------------------


async def test_three_strike_failure_raises_validation_error(
    monkeypatch: pytest.MonkeyPatch,
    hints: List[CatalogHint],
    audit_log_path: Path,
    extraction_service: LabExtractionService,
) -> None:
    bad = "not valid json at all"
    _patch_call(monkeypatch, [bad, bad, bad])

    with pytest.raises(ValidationError) as exc_info:
        await extraction_service.extract_text("doc", hints)
    assert "Lab extraction failed after 3 attempts" in str(exc_info.value.detail)


# ---------------------------------------------------------------------------
# Canonical hallucination → demote (does NOT count as retry)
# ---------------------------------------------------------------------------


async def test_canonical_hallucination_demoted_to_proposed(
    monkeypatch: pytest.MonkeyPatch,
    hints: List[CatalogHint],
    audit_log_path: Path,
    extraction_service: LabExtractionService,
) -> None:
    # LLM returns canonical_match that's not in the supplied hints.
    raw = json.dumps(_valid_payload(canonical_match="hallucinated_canonical"))
    _patch_call(monkeypatch, [raw])

    result = await extraction_service.extract_text("doc", hints)
    # NOT a retry — single call, single attempt.
    assert result.attempts == 1
    # But the demotion is logged.
    assert any("hallucinated" in msg or "demoted" in msg for msg in result.retried_due_to)
    m = result.payload.markers[0]
    assert m.canonical_match is None
    assert m.proposed_canonical == "hallucinated_canonical"


# ---------------------------------------------------------------------------
# Multimodal call shape — extract_pdf
# ---------------------------------------------------------------------------


async def test_extract_pdf_message_shape(
    monkeypatch: pytest.MonkeyPatch,
    hints: List[CatalogHint],
    audit_log_path: Path,
    extraction_service: LabExtractionService,
) -> None:
    raw = json.dumps(_valid_payload())
    capture: List[List[dict]] = []
    _patch_call(monkeypatch, [raw], capture=capture)

    pdf_bytes = b"%PDF-1.4\nfake\n%EOF"
    await extraction_service.extract_pdf(pdf_bytes, hints)

    assert len(capture) == 1
    user_msg = next(m for m in capture[0] if m["role"] == "user")
    parts = user_msg["content"]
    assert isinstance(parts, list)
    file_parts = [p for p in parts if p.get("type") == "file"]
    assert len(file_parts) == 1
    file_data: str = file_parts[0]["file"]["file_data"]
    assert file_data.startswith("data:application/pdf;base64,")


# ---------------------------------------------------------------------------
# Multimodal call shape — extract_image
# ---------------------------------------------------------------------------


async def test_extract_image_message_shape_jpeg(
    monkeypatch: pytest.MonkeyPatch,
    hints: List[CatalogHint],
    audit_log_path: Path,
    extraction_service: LabExtractionService,
) -> None:
    raw = json.dumps(_valid_payload())
    capture: List[List[dict]] = []
    _patch_call(monkeypatch, [raw], capture=capture)

    await extraction_service.extract_image(b"fake-jpeg-bytes", "image/jpeg", hints)

    user_msg = next(m for m in capture[0] if m["role"] == "user")
    parts = user_msg["content"]
    image_parts = [p for p in parts if p.get("type") == "image_url"]
    assert len(image_parts) == 1
    url: str = image_parts[0]["image_url"]["url"]
    assert url.startswith("data:image/jpeg;base64,")


async def test_extract_image_message_shape_png(
    monkeypatch: pytest.MonkeyPatch,
    hints: List[CatalogHint],
    audit_log_path: Path,
    extraction_service: LabExtractionService,
) -> None:
    raw = json.dumps(_valid_payload())
    capture: List[List[dict]] = []
    _patch_call(monkeypatch, [raw], capture=capture)

    await extraction_service.extract_image(b"fake-png-bytes", "image/png", hints)

    user_msg = next(m for m in capture[0] if m["role"] == "user")
    parts = user_msg["content"]
    image_parts = [p for p in parts if p.get("type") == "image_url"]
    assert image_parts[0]["image_url"]["url"].startswith("data:image/png;base64,")


# ---------------------------------------------------------------------------
# Audit log: one line per successful call
# ---------------------------------------------------------------------------


async def test_audit_log_writes_one_line_per_call(
    monkeypatch: pytest.MonkeyPatch,
    hints: List[CatalogHint],
    audit_log_path: Path,
    extraction_service: LabExtractionService,
) -> None:
    raw = json.dumps(_valid_payload())
    _patch_call(monkeypatch, [raw])

    await extraction_service.extract_text("doc", hints)

    assert audit_log_path.exists()
    lines = audit_log_path.read_text().strip().split("\n")
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["attempts"] == 1
    assert entry["confidence"] == 0.92
    assert "model" in entry
    assert "raw_response" in entry
    assert "ts" in entry


async def test_audit_log_records_failed_extraction(
    monkeypatch: pytest.MonkeyPatch,
    hints: List[CatalogHint],
    audit_log_path: Path,
    extraction_service: LabExtractionService,
) -> None:
    _patch_call(monkeypatch, ["garbage", "still garbage", "no really"])

    with pytest.raises(ValidationError):
        await extraction_service.extract_text("doc", hints)

    assert audit_log_path.exists()
    lines = audit_log_path.read_text().strip().split("\n")
    # Failure logs once (after all attempts exhausted).
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["attempts"] == 3
    assert len(entry["retried_due_to"]) >= 1
