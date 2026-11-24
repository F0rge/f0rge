from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass
from typing import BinaryIO
from zipfile import ZIP_DEFLATED, ZIP_STORED, BadZipFile, ZipFile
from zlib import error as InvalidCompressedData

from PIL import Image
from pydantic import ValidationError as SchemaError

from app.schemas.curated_catalogue import MAX_CATALOGUE_SKUS, CuratedCatalogueManifest
from f0rge_core.exceptions import ValidationError


MAX_ARCHIVE_BYTES = 40 * 1024 * 1024
MAX_UNPACKED_BYTES = 64 * 1024 * 1024
MAX_IMAGE_BYTES = 2 * 1024 * 1024
MAX_MANIFEST_BYTES = 256 * 1024
MAX_COMPRESSION_RATIO = 64


@dataclass(frozen=True)
class ReviewedCatalogue:
    manifest: CuratedCatalogueManifest
    images: dict[str, bytes]


def read_catalogue_archive(file: BinaryIO) -> ReviewedCatalogue:
    """Read a bounded owner upload without extracting paths from the archive."""
    file.seek(0, io.SEEK_END)
    if not 0 < file.tell() <= MAX_ARCHIVE_BYTES:
        raise ValidationError("Upload a catalogue ZIP smaller than 40 MiB")
    file.seek(0)
    try:
        with ZipFile(file) as archive:
            entries = archive.infolist()
            names = {entry.filename for entry in entries}
            if len(names) != len(entries) or len(entries) > 1 + 3 * MAX_CATALOGUE_SKUS:
                raise ValidationError("The archive has duplicate filenames or too many entries")
            if "manifest.json" not in names:
                raise ValidationError("The archive needs a manifest.json file")
            unpacked = 0
            for entry in entries:
                limit = MAX_MANIFEST_BYTES if entry.filename == "manifest.json" else MAX_IMAGE_BYTES
                if (
                    entry.compress_type not in (ZIP_STORED, ZIP_DEFLATED)
                    or entry.flag_bits & 1
                    or not 0 < entry.file_size <= limit
                    or entry.file_size > MAX_COMPRESSION_RATIO * entry.compress_size
                    or "/" in entry.filename
                    or "\\" in entry.filename
                ):
                    raise ValidationError("The ZIP contains an unsupported or oversized entry")
                unpacked += entry.file_size
            if unpacked > MAX_UNPACKED_BYTES:
                raise ValidationError("The unpacked catalogue exceeds 64 MiB")

            manifest = CuratedCatalogueManifest.model_validate_json(archive.read("manifest.json"))
            photos = [
                photo
                for sku in manifest.skus
                for photo in (*(sku.gallery or ()), *sku.supplemental_photos().values())
            ]
            photo_names = {photo.filename for photo in photos}
            if len(photo_names) != len(photos) or names != photo_names | {"manifest.json"}:
                raise ValidationError("Archive files must match the photos in the manifest")
            images: dict[str, bytes] = {}
            for photo in photos:
                data = archive.read(photo.filename)
                validate_jpeg(data)
                if hashlib.sha256(data).hexdigest() != photo.sha256:
                    raise ValidationError(
                        f"Photo checksum differs from the manifest: {photo.filename}"
                    )
                images[photo.filename] = data
            return ReviewedCatalogue(manifest=manifest, images=images)
    except SchemaError as exc:
        issue = exc.errors(include_input=False, include_url=False)[0]
        field = ".".join(str(part) for part in issue["loc"])
        raise ValidationError(f"Invalid catalogue manifest ({field}): {issue['msg']}") from exc
    except (
        BadZipFile,
        EOFError,
        OSError,
        InvalidCompressedData,
        Image.DecompressionBombError,
    ) as exc:
        raise ValidationError("The catalogue archive or its image data is unreadable") from exc


def validate_jpeg(data: bytes) -> None:
    with Image.open(io.BytesIO(data), formats=["JPEG"]) as image:
        if image.width * image.height > 16_000_000:
            raise ValidationError("JPG photos must have no more than 16 megapixels")
        image.load()
