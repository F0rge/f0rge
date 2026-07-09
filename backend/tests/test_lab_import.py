from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, List

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lab import Lab
from app.services import lab_attachment_storage as storage_module
from app.services import lab_extraction as extraction_module
from app.services.lab_attachment_storage import LabAttachmentStorage
from app.services.lab_catalog import LabMarkerCatalogService
from app.services.lab_extraction import LabExtractionService
from app.services.lab_import import LabImportService
from app.services.labs import LabsService


# ---------------------------------------------------------------------------
# Fixture: real DB + import service wired with real catalog/labs services
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def lab_import_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import settings

    async def _fake_resolve(db: AsyncSession) -> tuple[str, str]:
        return ("test-api-key", settings.openrouter_model)

    monkeypatch.setattr(
        "app.services.llm.factory.resolve_llm_credentials",
        _fake_resolve,
    )


@pytest.fixture
def import_service(
    async_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> LabImportService:
    # Redirect attachment storage root to tmp_path
    monkeypatch.setattr(storage_module, "_STORAGE_ROOT", str(tmp_path / "attachments"))
    # Redirect audit log to tmp_path
    monkeypatch.setattr(
        extraction_module,
        "_AUDIT_LOG_PATH",
        str(tmp_path / "extraction_audit.jsonl"),
    )

    labs = LabsService(async_db)
    catalog = LabMarkerCatalogService(async_db)
    extraction = LabExtractionService(async_db)
    storage = LabAttachmentStorage()
    return LabImportService(async_db, labs, catalog, extraction, storage)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _payload_for(
    *,
    name: str = "Test Blood Panel",
    canonical_match: str | None = "hemoglobin",
    proposed_canonical: str | None = None,
    value: float | None = 15.5,
    confidence: float = 0.9,
) -> dict:
    marker: dict[str, Any] = {
        "canonical_match": canonical_match,
        "proposed_canonical": proposed_canonical,
        "display_name": "Hemoglobin",
        "value": value,
        "value_text": None,
        "unit": "g/dL",
        "ref_low": 13.7,
        "ref_high": 17.2,
        "ref_text": None,
    }
    return {
        "lab": {
            "lab_date": "2026-05-01",
            "name": name,
            "type": "blood",
            "lab_location": None,
            "notes": None,
        },
        "markers": [marker],
        "confidence": confidence,
    }


def _patch_extraction(
    monkeypatch: pytest.MonkeyPatch,
    responses: List[str],
) -> None:
    """Patch the OpenRouter call so each invocation returns a canned response."""
    queue = list(responses)

    async def fake(messages: List[dict], model: str, api_key: str) -> str:
        if not queue:
            raise AssertionError("_call_openrouter called more times than expected")
        return queue.pop(0)

    monkeypatch.setattr(extraction_module, "_call_openrouter", fake)


# ---------------------------------------------------------------------------
# Markdown text import — first run + dedup + force
# ---------------------------------------------------------------------------


async def test_import_from_text_first_run_inserts(
    monkeypatch: pytest.MonkeyPatch,
    import_service: LabImportService,
) -> None:
    _patch_extraction(
        monkeypatch,
        [json.dumps(_payload_for(canonical_match=None, proposed_canonical="hemoglobin"))],
    )

    fixture = Path(__file__).parent / "fixtures" / "lab_blood.md"
    document = fixture.read_text()
    lab = await import_service.import_from_text(document, source_path="vault/lab_blood.md")

    assert lab.id is not None
    assert lab.source_kind == "vault_markdown" or lab.source_kind == "text"
    assert lab.source_path == "vault/lab_blood.md"
    assert len(lab.markers) == 1
    assert lab.markers[0].canonical_name == "hemoglobin"


async def test_import_from_text_second_run_is_noop(
    monkeypatch: pytest.MonkeyPatch,
    async_db: AsyncSession,
    import_service: LabImportService,
) -> None:
    # Idempotency must short-circuit BEFORE the LLM call so re-runs of the
    # vault import don't burn extraction credits on rows that already exist.
    # Only ONE response is queued; if a second call sneaks through, the patched
    # _call_openrouter will raise AssertionError and the test fails.
    raw = json.dumps(_payload_for(canonical_match=None, proposed_canonical="hemoglobin"))
    _patch_extraction(monkeypatch, [raw])

    fixture = Path(__file__).parent / "fixtures" / "lab_blood.md"
    document = fixture.read_text()

    lab1 = await import_service.import_from_text(document, source_path="vault/x.md")
    lab2 = await import_service.import_from_text(document, source_path="vault/x.md")

    assert lab1.id == lab2.id
    assert (await async_db.execute(select(func.count()).select_from(Lab))).scalar_one() == 1


async def test_import_from_text_force_replaces(
    monkeypatch: pytest.MonkeyPatch,
    async_db: AsyncSession,
    import_service: LabImportService,
) -> None:
    first = json.dumps(_payload_for(name="Original", value=15.5))
    second = json.dumps(_payload_for(name="Replacement", value=12.0))
    _patch_extraction(monkeypatch, [first, second])

    document = "any document"
    lab1 = await import_service.import_from_text(document, source_path="vault/x.md")
    assert lab1.name == "Original"
    lab2 = await import_service.import_from_text(document, source_path="vault/x.md", force=True)

    # force=True deletes the old row and inserts a new one with replacement data.
    assert lab2.name == "Replacement"
    assert (await async_db.execute(select(func.count()).select_from(Lab))).scalar_one() == 1
    remaining = (await async_db.execute(select(Lab))).scalars().first()
    assert remaining.name == "Replacement"


# ---------------------------------------------------------------------------
# PDF upload — source_kind, attachment_path, file on disk, SHA dedup
# ---------------------------------------------------------------------------


async def test_import_from_pdf_persists_file_and_sets_metadata(
    monkeypatch: pytest.MonkeyPatch,
    import_service: LabImportService,
) -> None:
    raw = json.dumps(_payload_for())
    _patch_extraction(monkeypatch, [raw])

    pdf_bytes = b"%PDF-1.4\nfake pdf body\n%EOF"
    lab = await import_service.import_from_pdf(pdf_bytes, "test.pdf")

    assert lab.source_kind == "pdf"
    assert lab.attachment_path is not None
    # File should actually exist on disk.
    assert os.path.exists(lab.attachment_path)
    # source_path was auto-derived from SHA256.
    assert lab.source_path is not None
    assert lab.source_path.startswith("upload:")


async def test_import_from_pdf_sha256_dedup(
    monkeypatch: pytest.MonkeyPatch,
    async_db: AsyncSession,
    import_service: LabImportService,
) -> None:
    # Re-uploading identical PDF bytes must short-circuit BEFORE the LLM call.
    # Only ONE response queued; the patched _call_openrouter raises on second.
    raw = json.dumps(_payload_for())
    _patch_extraction(monkeypatch, [raw])

    pdf_bytes = b"%PDF-1.4\nidentical bytes\n%EOF"

    lab1 = await import_service.import_from_pdf(pdf_bytes, "first-name.pdf")
    lab2 = await import_service.import_from_pdf(pdf_bytes, "second-name.pdf")

    assert lab1.id == lab2.id
    assert (await async_db.execute(select(func.count()).select_from(Lab))).scalar_one() == 1


async def test_import_from_pdf_with_source_path_skips_extract_on_redo(
    monkeypatch: pytest.MonkeyPatch,
    async_db: AsyncSession,
    import_service: LabImportService,
) -> None:
    # CLI re-run scenario: same vault-derived source_path on retry should NOT
    # re-hit the LLM. This is the regression that caused PR #43 + import #2 to
    # burn three failed-401 attempts on labs we'd already imported.
    raw = json.dumps(_payload_for())
    _patch_extraction(monkeypatch, [raw])

    pdf_bytes = b"%PDF-1.4\nfirst-bytes\n%EOF"
    src = "raw/2026-01-01_Exame-X.pdf"

    lab1 = await import_service.import_from_pdf(pdf_bytes, "x.pdf", source_path=src)
    # Different bytes but same explicit source_path → still a duplicate.
    different_bytes = b"%PDF-1.4\nDIFFERENT-bytes\n%EOF"
    lab2 = await import_service.import_from_pdf(different_bytes, "x.pdf", source_path=src)

    assert lab1.id == lab2.id
    assert (await async_db.execute(select(func.count()).select_from(Lab))).scalar_one() == 1


async def test_import_from_pdf_low_confidence_sets_needs_review(
    monkeypatch: pytest.MonkeyPatch,
    import_service: LabImportService,
) -> None:
    raw = json.dumps(_payload_for(confidence=0.5))
    _patch_extraction(monkeypatch, [raw])

    pdf_bytes = b"%PDF-1.4\nlow-conf\n%EOF"
    lab = await import_service.import_from_pdf(pdf_bytes, "lowconf.pdf")
    assert lab.review_status == "needs_review"


async def test_import_from_pdf_high_confidence_confirmed(
    monkeypatch: pytest.MonkeyPatch,
    import_service: LabImportService,
) -> None:
    raw = json.dumps(_payload_for(confidence=0.95))
    _patch_extraction(monkeypatch, [raw])

    pdf_bytes = b"%PDF-1.4\nhighconf\n%EOF"
    lab = await import_service.import_from_pdf(pdf_bytes, "highconf.pdf")
    assert lab.review_status == "confirmed"


# ---------------------------------------------------------------------------
# Image upload
# ---------------------------------------------------------------------------


async def test_import_from_image_persists_file_and_sets_metadata(
    monkeypatch: pytest.MonkeyPatch,
    import_service: LabImportService,
) -> None:
    raw = json.dumps(_payload_for())
    _patch_extraction(monkeypatch, [raw])

    image_bytes = b"fake-jpeg-bytes"
    lab = await import_service.import_from_image(image_bytes, "image/jpeg", "scan.jpg")

    assert lab.source_kind == "image"
    assert lab.attachment_path is not None
    assert os.path.exists(lab.attachment_path)
    assert lab.attachment_path.endswith(".jpg")


# ---------------------------------------------------------------------------
# Imaging-only markdown (no numeric markers) — still imports
# ---------------------------------------------------------------------------


async def test_import_imaging_no_markers(
    monkeypatch: pytest.MonkeyPatch,
    import_service: LabImportService,
) -> None:
    # Imaging payload: zero markers, type="imaging".
    imaging_payload: dict = {
        "lab": {
            "lab_date": "2022-06-15",
            "name": "Brain CT",
            "type": "imaging",
            "lab_location": "Hospital da Luz",
            "notes": "Normal brain CT scan",
        },
        "markers": [],
        "confidence": 0.9,
    }
    _patch_extraction(monkeypatch, [json.dumps(imaging_payload)])

    fixture = Path(__file__).parent / "fixtures" / "lab_imaging.md"
    document = fixture.read_text()
    lab = await import_service.import_from_text(document, source_path="vault/lab_imaging.md")

    assert lab.type == "imaging"
    assert lab.markers == []
    assert lab.notes == "Normal brain CT scan"
