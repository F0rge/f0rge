from __future__ import annotations

import datetime
import re
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.labs import LabCRUD
from app.exceptions import NotFoundError, ValidationError
from app.models.lab import Lab
from app.models.lab_marker import LabMarker
from app.schemas.lab import LabCreate, LabUpdate, LabMarkerCreate
from app.tenant import current_user_id

_ABNORMAL_REF_RE = re.compile(
    r"\b(positive|elevated|reactive|abnormal|class\s*[>=]\s*\d|high|present)\b",
    re.IGNORECASE,
)

# Unidirectional reference-range patterns commonly seen in lab reports.
# Captures things like "<5.18", ">60", "<=29", ">=0.27", "< 4.1", "≤14.0".
# The numeric value is in group(1); leading whitespace and comparison
# operators are normalised so both "<", "<=", "≤" are treated as "less-than".
_REF_TEXT_LESS_RE = re.compile(r"^\s*[<≤]=?\s*(-?\d+(?:[.,]\d+)?)\s*$")
_REF_TEXT_GREATER_RE = re.compile(r"^\s*[>≥]=?\s*(-?\d+(?:[.,]\d+)?)\s*$")


def _parse_unidirectional_ref(
    ref_text: Optional[str],
) -> tuple[Optional[float], Optional[float]]:
    """Parse a unidirectional ref_text string into (implied_low, implied_high).

    Examples:
      "<5.18"  -> (None, 5.18)
      "<=29"   -> (None, 29.0)
      ">60"    -> (60.0, None)
      ">=0.27" -> (0.27, None)
    Returns (None, None) for non-inequality text ("Negative", "Normal", complex ranges).
    """
    if not ref_text:
        return (None, None)
    text = ref_text.replace(",", ".")
    m = _REF_TEXT_LESS_RE.match(text)
    if m:
        try:
            return (None, float(m.group(1)))
        except ValueError:
            return (None, None)
    m = _REF_TEXT_GREATER_RE.match(text)
    if m:
        try:
            return (float(m.group(1)), None)
        except ValueError:
            return (None, None)
    return (None, None)


class LabsService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = LabCRUD(db)

    async def list_labs(
        self,
        start_date: Optional[datetime.date] = None,
        end_date: Optional[datetime.date] = None,
        lab_type: Optional[str] = None,
    ) -> List[Lab]:
        return await self.crud.list(start_date, end_date, lab_type)

    async def get_lab(self, lab_id: int) -> Lab:
        lab = await self.crud.get_by_id(lab_id)
        if lab is None:
            raise NotFoundError("Lab not found.")
        return lab

    async def create_lab(
        self,
        data: LabCreate,
        *,
        extraction_meta: Optional[dict] = None,
    ) -> Lab:
        meta = extraction_meta or {}
        lab = Lab(
            user_id=current_user_id(),
            lab_date=data.lab_date,
            name=data.name,
            type=data.type,
            lab_location=data.lab_location,
            source_kind=meta.get("source_kind", data.source_kind),
            source_path=data.source_path,
            attachment_path=meta.get("attachment_path", data.attachment_path),
            raw_text=meta.get("raw_text", data.raw_text),
            extraction_model=meta.get("extraction_model"),
            extraction_confidence=meta.get("extraction_confidence"),
            review_status=meta.get("review_status", "confirmed"),
            notes=data.notes,
        )
        self.crud.add(lab)
        await self.crud.flush()

        for marker_data in data.markers:
            await self._insert_marker(lab.id, marker_data)

        return await self.crud.commit_refresh(lab)

    async def update_lab(self, lab_id: int, data: LabUpdate) -> Lab:
        lab = await self.get_lab(lab_id)
        patch = data.model_dump(exclude_unset=True)
        markers_patch = patch.pop("markers", None)

        for field, value in patch.items():
            setattr(lab, field, value)

        if markers_patch is not None:
            # Replace-all strategy: delete existing, re-insert.
            for existing in list(lab.markers):
                await self.crud.delete(existing)
            await self.crud.flush()
            for marker_data in markers_patch:
                if isinstance(marker_data, dict):
                    marker_data = LabMarkerCreate(**marker_data)
                await self._insert_marker(lab.id, marker_data)

        lab.updated_at = datetime.datetime.utcnow()
        return await self.crud.commit_refresh(lab)

    async def delete_lab(self, lab_id: int) -> None:
        lab = await self.get_lab(lab_id)
        await self.crud.delete_and_commit(lab)

    async def _insert_marker(self, lab_id: int, data: LabMarkerCreate) -> None:
        catalog_id = data.catalog_id
        canonical_name = data.canonical_name

        if not catalog_id:
            from app.services.lab_catalog import LabMarkerCatalogService

            if not canonical_name and not data.display_name:
                raise ValidationError("Marker requires canonical_name or display_name.")
            lookup_name = canonical_name or data.display_name
            catalog_entry = await LabMarkerCatalogService(self.db).resolve_or_create(
                name=lookup_name,
                display_name=data.display_name,
                units=[data.unit] if data.unit else [],
            )
            catalog_id = catalog_entry.id
            canonical_name = catalog_entry.canonical_name

        flag = self.compute_flag(
            value=data.value,
            value_text=data.value_text,
            ref_low=data.ref_low,
            ref_high=data.ref_high,
            ref_text=data.ref_text,
        )
        marker = LabMarker(
            user_id=current_user_id(),
            lab_id=lab_id,
            catalog_id=catalog_id,
            canonical_name=canonical_name,
            display_name=data.display_name,
            value=data.value,
            value_text=data.value_text,
            unit=data.unit,
            ref_low=data.ref_low,
            ref_high=data.ref_high,
            ref_text=data.ref_text,
            flag=flag,
        )
        await self.crud.add_and_flush(marker)

    @staticmethod
    def compute_flag(
        value: Optional[float],
        value_text: Optional[str],
        ref_low: Optional[float],
        ref_high: Optional[float],
        ref_text: Optional[str],
    ) -> str:
        """Compute the clinical flag for a marker reading."""
        if value is None:
            if ref_text and value_text:
                if _ABNORMAL_REF_RE.search(ref_text) or _ABNORMAL_REF_RE.search(value_text):
                    return "abnormal"
            return "unknown"

        if ref_low is None and ref_high is None and ref_text:
            ref_low, ref_high = _parse_unidirectional_ref(ref_text)

        if ref_low is not None and ref_high is not None:
            if value < ref_low:
                return "low"
            if value > ref_high:
                return "high"
            return "normal"

        if ref_low is not None:
            return "low" if value < ref_low else "normal"

        if ref_high is not None:
            return "high" if value > ref_high else "normal"

        return "unknown"
