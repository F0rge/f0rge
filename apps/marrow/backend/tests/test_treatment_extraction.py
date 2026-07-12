from __future__ import annotations

import json
from pathlib import Path
from typing import Any, List

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from f0rge_core.exceptions import ValidationError
from app.services import treatment_extraction as extraction_module
from app.services.treatment_extraction import TreatmentExtractionService


def _valid_payload(
    *,
    name: str = "Rifaximin",
    confidence: float = 0.9,
    treatments: list[dict[str, Any]] | None = None,
) -> dict:
    if treatments is None:
        treatments = [
            {
                "name": name,
                "type": "prescription",
                "start_date": "2026-05-01",
                "end_date": None,
                "dose": "550mg",
                "doses_per_day": 3,
                "notes": "Take with food",
                "group_name": None,
            }
        ]
    return {"treatments": treatments, "confidence": confidence}


@pytest.fixture(autouse=True)
def treatment_extraction_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_resolve(db: AsyncSession) -> tuple[str, str]:
        return ("test-api-key", settings.openrouter_model)

    monkeypatch.setattr(
        "app.services.llm.factory.resolve_llm_credentials",
        _fake_resolve,
    )


@pytest.fixture
def extraction_service(async_db: AsyncSession) -> TreatmentExtractionService:
    return TreatmentExtractionService(async_db)


@pytest.fixture
def audit_log_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    path = tmp_path / "extraction_audit.jsonl"
    monkeypatch.setattr(extraction_module, "_AUDIT_LOG_PATH", str(path))
    return path


def _patch_call(
    monkeypatch: pytest.MonkeyPatch,
    responses: List[str | Exception] | str,
) -> None:
    queue = list(responses) if isinstance(responses, list) else [responses]

    async def fake(messages: List[dict], model: str, api_key: str) -> str:
        if not queue:
            raise AssertionError("fake _call_openrouter called more times than expected")
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(extraction_module, "_call_openrouter", fake)


async def test_extract_pdf_single_treatment(
    monkeypatch: pytest.MonkeyPatch,
    audit_log_path: Path,
    extraction_service: TreatmentExtractionService,
) -> None:
    raw = json.dumps(_valid_payload())
    _patch_call(monkeypatch, [raw])

    result = await extraction_service.extract_pdf(b"%PDF-1.4", filename="rx.pdf")

    assert result.attempts == 1
    assert len(result.payload.treatments) == 1
    t = result.payload.treatments[0]
    assert t.name == "Rifaximin"
    assert t.type == "prescription"
    assert t.doses_per_day == 3
    assert result.payload.confidence == 0.9


async def test_extract_multiple_treatments(
    monkeypatch: pytest.MonkeyPatch,
    audit_log_path: Path,
    extraction_service: TreatmentExtractionService,
) -> None:
    raw = json.dumps(
        _valid_payload(
            treatments=[
                {
                    "name": "Drug A",
                    "type": "prescription",
                    "start_date": "2026-05-01",
                    "end_date": None,
                    "dose": "10mg",
                    "doses_per_day": 1,
                    "notes": None,
                    "group_name": None,
                },
                {
                    "name": "Drug B",
                    "type": "antibiotic",
                    "start_date": "2026-05-01",
                    "end_date": "2026-05-14",
                    "dose": "500mg",
                    "doses_per_day": 2,
                    "notes": None,
                    "group_name": "Course 1",
                },
            ]
        )
    )
    _patch_call(monkeypatch, [raw])

    result = await extraction_service.extract_pdf(b"%PDF-1.4")

    assert len(result.payload.treatments) == 2
    assert result.payload.treatments[1].group_name == "Course 1"


async def test_extract_empty_treatments_returns(
    monkeypatch: pytest.MonkeyPatch,
    audit_log_path: Path,
    extraction_service: TreatmentExtractionService,
) -> None:
    raw = json.dumps({"treatments": [], "confidence": 0.0})
    _patch_call(monkeypatch, [raw])

    result = await extraction_service.extract_pdf(b"%PDF-1.4")

    assert result.attempts == 1
    assert result.payload.treatments == []
    assert result.payload.confidence == 0.0


async def test_preview_upload_unsupported_mime(
    extraction_service: TreatmentExtractionService,
) -> None:
    with pytest.raises(ValidationError, match="Unsupported MIME type"):
        await extraction_service.preview_upload(b"data", "text/plain", "file.txt")


async def test_preview_upload_dispatches_pdf(
    monkeypatch: pytest.MonkeyPatch,
    audit_log_path: Path,
    extraction_service: TreatmentExtractionService,
) -> None:
    raw = json.dumps(_valid_payload())
    _patch_call(monkeypatch, [raw])

    result = await extraction_service.preview_upload(b"%PDF-1.4", "application/pdf", "rx.pdf")
    assert result.payload.treatments[0].name == "Rifaximin"


async def test_default_start_date_when_missing(
    monkeypatch: pytest.MonkeyPatch,
    audit_log_path: Path,
    extraction_service: TreatmentExtractionService,
) -> None:
    raw = json.dumps(
        _valid_payload(
            treatments=[
                {
                    "name": "Drug A",
                    "type": "prescription",
                    "start_date": None,
                    "end_date": None,
                    "dose": None,
                    "doses_per_day": None,
                    "notes": None,
                    "group_name": None,
                }
            ]
        )
    )
    _patch_call(monkeypatch, [raw])

    result = await extraction_service.extract_pdf(b"%PDF-1.4")
    assert result.payload.treatments[0].start_date is not None
