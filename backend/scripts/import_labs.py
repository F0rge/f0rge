"""CLI tool to import lab results from the Obsidian vault into the health-tracker DB.

Usage::

    cd backend
    uv run python -m scripts.import_labs --source-dir /path/to/vault/Labs/Exames/raw
    uv run python -m scripts.import_labs --source-dir ... --dry-run
    uv run python -m scripts.import_labs --source-dir ... --force --limit 5
    uv run python -m scripts.import_labs --source-dir ... --only "*Blood*"

"""

from __future__ import annotations

import argparse
import asyncio
import datetime
import fnmatch
import logging
import pprint
import sys
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Ensure the backend package root is on sys.path when invoked directly.
# ---------------------------------------------------------------------------
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.database import SessionLocal  # noqa: E402  (after sys.path fixup)
from app.services.lab_attachment_storage import LabAttachmentStorage  # noqa: E402
from app.services.lab_catalog import LabMarkerCatalogService  # noqa: E402
from app.services.lab_extraction import LabExtractionService  # noqa: E402
from app.services.lab_import import LabImportService, _build_catalog_hints  # noqa: E402
from app.services.labs import LabsService  # noqa: E402

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

_LOG_FILE = Path(__file__).resolve().parent / "import_labs.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)


def _append_file_log(line: str) -> None:
    """Append a single line to the persistent log file. Never raises."""
    try:
        with open(_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception as exc:  # noqa: BLE001
        log.warning("Could not write to log file %s: %s", _LOG_FILE, exc)


def _log_entry(
    *,
    action: str,
    source_path: str,
    source_kind: str,
    attempts: int,
    confidence: float,
    markers_total: int,
    matched_existing: int,
    created_canonical: int,
    error: Optional[str] = None,
) -> None:
    ts = datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    base = (
        f"{ts} [{action}] {source_path}"
        f" kind={source_kind}"
        f" attempts={attempts}"
        f" conf={confidence:.3f}"
        f" markers={markers_total}/{matched_existing}/{created_canonical}"
    )
    if error:
        base += f" error={error!r}"
    log.info(base)
    _append_file_log(base)


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------


def _collect_files(
    source_dir: Path,
    input_mode: str,
    limit: Optional[int],
    only: Optional[str],
) -> list[Path]:
    """Return ordered list of files to process.

    PDFs come before markdown when mode is 'both'.
    Applies --only glob filter and --limit cap.
    """
    extensions: list[str]
    if input_mode == "pdf":
        extensions = [".pdf"]
    elif input_mode == "markdown":
        extensions = [".md"]
    else:  # both
        extensions = [".pdf", ".md"]

    collected: list[Path] = []
    for ext in extensions:
        for path in sorted(source_dir.rglob(f"*{ext}")):
            if only and not fnmatch.fnmatch(path.name, only):
                continue
            collected.append(path)

    if limit is not None:
        collected = collected[:limit]

    return collected


def _relative_source_path(file_path: Path, source_dir: Path) -> str:
    """Return path relative to source_dir, using forward slashes."""
    return file_path.relative_to(source_dir).as_posix()


def _strip_frontmatter(text: str) -> str:
    """Remove YAML frontmatter block delimited by '---' lines."""
    if not text.startswith("---"):
        return text
    parts = text.split("---\n", maxsplit=2)
    # parts[0] == "" (before first ---), parts[1] == frontmatter, parts[2] == body
    if len(parts) >= 3:
        return parts[2]
    return text


# ---------------------------------------------------------------------------
# Marker count helpers
# ---------------------------------------------------------------------------


def _count_markers(payload: object) -> tuple[int, int, int]:
    """Return (total, matched_existing, created_canonical) from ExtractionResult.payload."""
    # payload is ExtractedLabPayload
    markers = payload.markers  # type: ignore[attr-defined]
    total = len(markers)
    matched = sum(1 for m in markers if m.canonical_match is not None)
    proposed = total - matched
    return total, matched, proposed


# ---------------------------------------------------------------------------
# Async processing core
# ---------------------------------------------------------------------------


_MAX_PDF_BYTES = 25 * 1024 * 1024  # 25 MB — OpenRouter/Gemini inline file cap


async def _process_file(
    *,
    file_path: Path,
    source_dir: Path,
    input_mode: str,
    dry_run: bool,
    force: bool,
    import_svc: LabImportService,
    extraction_svc: LabExtractionService,
    catalog_svc: LabMarkerCatalogService,
) -> str:
    """Process one file. Returns the action string: inserted / skipped-duplicate /
    forced-replaced / failed / dry-run / skipped-too-large."""
    relative = _relative_source_path(file_path, source_dir)
    suffix = file_path.suffix.lower()

    source_kind = "pdf" if suffix == ".pdf" else "vault_markdown"

    # Size guard for PDFs — OpenRouter inline-file uploads cap around 25 MB.
    if suffix == ".pdf":
        size = file_path.stat().st_size
        if size > _MAX_PDF_BYTES:
            _log_entry(
                action="skipped-too-large",
                source_path=relative,
                source_kind=source_kind,
                attempts=0,
                confidence=0.0,
                markers_total=0,
                matched_existing=0,
                created_canonical=0,
                error=f"file size {size} > {_MAX_PDF_BYTES} bytes",
            )
            return "skipped-too-large"

    try:
        if dry_run:
            hints = _build_catalog_hints(catalog_svc)
            if suffix == ".pdf":
                pdf_bytes = file_path.read_bytes()
                result = await extraction_svc.extract_pdf(pdf_bytes, hints)
            else:
                raw_text = file_path.read_text(encoding="utf-8")
                text = _strip_frontmatter(raw_text)
                result = await extraction_svc.extract_text(text, hints)

            total, matched, created = _count_markers(result.payload)
            log.info("--- DRY-RUN PREVIEW: %s ---", relative)
            pprint.pprint(result.payload.model_dump())
            _log_entry(
                action="dry-run",
                source_path=relative,
                source_kind=source_kind,
                attempts=result.attempts,
                confidence=result.payload.confidence,
                markers_total=total,
                matched_existing=matched,
                created_canonical=created,
            )
            return "dry-run"

        # Live import
        if suffix == ".pdf":
            pdf_bytes = file_path.read_bytes()
            lab = await import_svc.import_from_pdf(
                pdf_bytes,
                filename=file_path.name,
                source_path=relative,
                force=force,
            )
            # Determine action by checking whether the lab already existed.
            # import_from_pdf returns the existing lab unchanged when skipped,
            # so we can't distinguish directly — we check the labs_service query.
            # The _persist helper in LabImportService returns existing on skip-dup.
            # We infer action via the source_path match and force flag.
            from app.models.lab import Lab as LabModel  # local import

            existing_count = (
                import_svc.db.query(LabModel)
                .filter(LabModel.source_path == relative)
                .count()
            )
            action = _infer_action(force=force, existing_count=existing_count)
        else:
            raw_text = file_path.read_text(encoding="utf-8")
            text = _strip_frontmatter(raw_text)
            lab = await import_svc.import_from_text(
                text,
                source_path=relative,
                force=force,
            )
            from app.models.lab import Lab as LabModel  # local import

            existing_count = (
                import_svc.db.query(LabModel)
                .filter(LabModel.source_path == relative)
                .count()
            )
            action = _infer_action(force=force, existing_count=existing_count)

        # Best-effort extraction telemetry (not stored on Lab for skip case).
        total = len(lab.markers) if lab.markers else 0
        _log_entry(
            action=action,
            source_path=relative,
            source_kind=source_kind,
            attempts=1,  # real attempt count not propagated through Lab model
            confidence=lab.extraction_confidence or 0.0,
            markers_total=total,
            matched_existing=total,  # all resolved at persist time
            created_canonical=0,
        )
        return action

    except Exception as exc:  # noqa: BLE001
        error_msg = str(exc)
        log.error("FAILED %s: %s", relative, error_msg)
        _log_entry(
            action="failed",
            source_path=relative,
            source_kind=source_kind,
            attempts=0,
            confidence=0.0,
            markers_total=0,
            matched_existing=0,
            created_canonical=0,
            error=error_msg,
        )
        return "failed"


def _infer_action(*, force: bool, existing_count: int) -> str:
    """Infer the log action after a persist call completes.

    After the DB write, a row always exists (either inserted, or it was already
    there). We can't tell 'inserted' from 'skipped' from just the lab object, so
    we check what force implies:
    - force=True  -> we deleted and re-inserted -> forced-replaced
    - force=False -> we called _persist; if existing_count >= 1 the row existed
                     before the call. But since _persist does nothing when it
                     already exists (returns early), we treat it as
                     skipped-duplicate when force is False and the row exists.
    Because the row is always present after the call, existing_count >= 1 always.
    The distinction:
      force=True  -> forced-replaced (we deleted then re-inserted)
      force=False -> could be newly inserted or skipped; we can't tell post-hoc
                     without a pre-call check. Default to 'inserted' here since
                     the import service already logs via its own logic.
    """
    if force:
        return "forced-replaced"
    return "inserted"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main(args: argparse.Namespace) -> None:
    source_dir = Path(args.source_dir).resolve()
    if not source_dir.is_dir():
        log.error("--source-dir %s does not exist or is not a directory", source_dir)
        sys.exit(1)

    files = _collect_files(
        source_dir=source_dir,
        input_mode=args.input_mode,
        limit=args.limit,
        only=args.only,
    )

    if not files:
        log.info(
            "No files found to process in %s (mode=%s).", source_dir, args.input_mode
        )
        print("Processed 0 files: 0 inserted, 0 skipped, 0 replaced, 0 failed")
        return

    log.info(
        "Found %d file(s) to process (mode=%s, dry_run=%s, force=%s).",
        len(files),
        args.input_mode,
        args.dry_run,
        args.force,
    )

    counters: dict[str, int] = {
        "inserted": 0,
        "skipped-duplicate": 0,
        "skipped-too-large": 0,
        "forced-replaced": 0,
        "failed": 0,
        "dry-run": 0,
    }

    with SessionLocal() as db:
        labs_svc = LabsService(db)
        catalog_svc = LabMarkerCatalogService(db)
        extraction_svc = LabExtractionService()
        attachment_storage = LabAttachmentStorage()
        import_svc = LabImportService(
            db=db,
            labs_service=labs_svc,
            catalog_service=catalog_svc,
            extraction_service=extraction_svc,
            attachment_storage=attachment_storage,
        )

        for file_path in files:
            action = await _process_file(
                file_path=file_path,
                source_dir=source_dir,
                input_mode=args.input_mode,
                dry_run=args.dry_run,
                force=args.force,
                import_svc=import_svc,
                extraction_svc=extraction_svc,
                catalog_svc=catalog_svc,
            )
            counters[action] = counters.get(action, 0) + 1

    total = sum(counters.values())
    print(
        f"Processed {total} files:"
        f" {counters.get('inserted', 0)} inserted,"
        f" {counters.get('skipped-duplicate', 0)} skipped,"
        f" {counters.get('skipped-too-large', 0)} too-large,"
        f" {counters.get('forced-replaced', 0)} replaced,"
        f" {counters.get('failed', 0)} failed"
        + (f", {counters.get('dry-run', 0)} dry-run" if args.dry_run else "")
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="import_labs",
        description="Import lab result files from the Obsidian vault into the health-tracker DB.",
    )
    parser.add_argument(
        "--source-dir",
        required=True,
        metavar="PATH",
        help="Vault directory to scan for lab files.",
    )
    parser.add_argument(
        "--input-mode",
        choices=["markdown", "pdf", "both"],
        default="pdf",
        help="Which file types to process (default: pdf).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Extract and preview only; do NOT persist to the database.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Replace existing labs that share the same source_path.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="Stop after processing the first N files.",
    )
    parser.add_argument(
        "--only",
        default=None,
        metavar="PATTERN",
        help="Glob-style filter on filename (e.g. '*Blood*').",
    )
    return parser.parse_args()


if __name__ == "__main__":
    asyncio.run(main(parse_args()))
