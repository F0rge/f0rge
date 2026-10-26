"""Validate and unpack a Cin7 export upload.

Accepts the collaborator zip (a ``cin7-export/`` folder inside) or the folder's
CSV and XLSX files. Extraction refuses path traversal, symlinks, and zip bombs.
"""

from __future__ import annotations

import hashlib
import io
import os
import stat
import zipfile
from pathlib import Path
from typing import Optional

from f0rge_core.exceptions import ValidationError

MAX_UPLOAD_BYTES = 100 * 1024 * 1024
MIN_UPLOAD_LIMIT_BYTES = 25 * 1024 * 1024
MAX_ZIP_MEMBERS = 80
MAX_UNCOMPRESSED_BYTES = 512 * 1024 * 1024
MAX_COMPRESSION_RATIO = 100
ALLOWED_SUFFIXES = {".csv", ".xlsx"}
_SKIP_PARTS = {"__macosx", ".ds_store", "thumbs.db"}


def assert_upload_limit() -> None:
    if MAX_UPLOAD_BYTES < MIN_UPLOAD_LIMIT_BYTES:
        raise RuntimeError("Cin7 upload limit is below 25 MB")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _suffix(name: str) -> str:
    return Path(name).suffix.lower()


def _parts(name: str) -> list[str]:
    cleaned = name.replace("\\", "/").strip()
    if cleaned.startswith("/"):
        raise ValidationError("Zip entry is an absolute path")
    parts = [part for part in cleaned.split("/") if part not in ("", ".")]
    if any(part == ".." for part in parts):
        raise ValidationError("Zip entry escapes the export directory")
    return parts


def _skipped(parts: list[str]) -> bool:
    lowered = [part.lower() for part in parts]
    if any(part in _SKIP_PARTS for part in lowered):
        return True
    return lowered[:1] == ["__macosx"]


def _check_member(info: zipfile.ZipInfo) -> Optional[list[str]]:
    if info.flag_bits & 0x1:
        raise ValidationError("Zip is encrypted")
    mode = info.external_attr >> 16
    if stat.S_ISLNK(mode):
        raise ValidationError("Zip contains a symlink")
    parts = _parts(info.filename)
    if not parts or _skipped(parts):
        return None
    if info.is_dir():
        return parts
    suffix = _suffix(parts[-1])
    if suffix not in ALLOWED_SUFFIXES:
        raise ValidationError(f"Zip entry {parts[-1]} is not a csv or xlsx file")
    if info.file_size < 0:
        raise ValidationError("Zip entry has a negative size")
    if info.compress_size > 0 and info.file_size > 1024 * 1024:
        ratio = info.file_size / info.compress_size
        if ratio > MAX_COMPRESSION_RATIO:
            raise ValidationError("Zip looks like a zip bomb")
    return parts


def validate_zip(data: bytes) -> None:
    assert_upload_limit()
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValidationError("File exceeds the 100 MB upload limit")
    if not zipfile.is_zipfile(io.BytesIO(data)):
        raise ValidationError("Upload is not a zip file")
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise ValidationError("Upload is not a zip file") from exc
    kept = 0
    uncompressed = 0
    with archive:
        for info in archive.infolist():
            parts = _check_member(info)
            if parts is None or info.is_dir():
                continue
            kept += 1
            uncompressed += info.file_size
            if kept > MAX_ZIP_MEMBERS:
                raise ValidationError("Zip has too many files")
            if uncompressed > MAX_UNCOMPRESSED_BYTES:
                raise ValidationError("Zip expands past the size limit")
    if kept == 0:
        raise ValidationError("Zip does not contain csv or xlsx files")


def _destination(dest: Path, parts: list[str]) -> Path:
    root = dest.resolve()
    target = root.joinpath(*parts).resolve()
    if target != root and not str(target).startswith(str(root) + os.sep):
        raise ValidationError("Zip entry escapes the export directory")
    return target


def extract_zip(data: bytes, dest: Path) -> None:
    validate_zip(data)
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for info in archive.infolist():
            parts = _check_member(info)
            if parts is None:
                continue
            target = _destination(dest, parts)
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info, "r") as source, target.open("wb") as handle:
                remaining = MAX_UNCOMPRESSED_BYTES
                while True:
                    block = source.read(1024 * 1024)
                    if not block:
                        break
                    remaining -= len(block)
                    if remaining < 0:
                        raise ValidationError("Zip expands past the size limit")
                    handle.write(block)


def locate_export_dir(root: Path) -> Path:
    """Prefer the collaborator's ``cin7-export`` folder when the zip has one."""
    nested = root / "cin7-export"
    if nested.is_dir():
        return nested
    files = [path for path in root.iterdir() if path.is_file()]
    dirs = [path for path in root.iterdir() if path.is_dir() and path.name != "__MACOSX"]
    data_files = [path for path in files if path.suffix.lower() in ALLOWED_SUFFIXES]
    if data_files:
        return root
    if len(dirs) == 1:
        return dirs[0]
    raise ValidationError("Zip does not contain a Cin7 export folder")


def pack_export_files(named: list[tuple[str, bytes]]) -> bytes:
    """Store loose export files as one zip. Names are sorted so the hash is stable."""
    if not named:
        raise ValidationError("Choose a Cin7 export zip or the export files")
    buffer = io.BytesIO()
    seen: set[str] = set()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, payload in sorted(named, key=lambda item: item[0].lower()):
            parts = _parts(name)
            if len(parts) != 1 or _suffix(parts[0]) not in ALLOWED_SUFFIXES:
                raise ValidationError(f"{name} is not a csv or xlsx file")
            if parts[0] in seen:
                raise ValidationError(f"Duplicate file name {parts[0]}")
            seen.add(parts[0])
            archive.writestr(f"cin7-export/{parts[0]}", payload)
    data = buffer.getvalue()
    validate_zip(data)
    return data
