from __future__ import annotations

import datetime
import re
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.exceptions import NotFoundError, ValidationError
from app.models.lab import Lab
from app.models.lab_marker import LabMarker
from app.schemas.lab import LabCreate, LabUpdate, LabMarkerCreate

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

    async def list_labs(
        self,
        start_date: Optional[datetime.date] = None,
        end_date: Optional[datetime.date] = None,
        lab_type: Optional[str] = None,
    ) -> List[Lab]:
        stmt = select(Lab).options(selectinload(Lab.markers))
        if start_date is not None:
            stmt = stmt.where(Lab.lab_date >= start_date)
        if end_date is not None:
            stmt = stmt.where(Lab.lab_date <= end_date)
        if lab_type is not None:
            stmt = stmt.where(Lab.type == lab_type)
        stmt = stmt.order_by(Lab.lab_date.desc())
        return list((await self.db.execute(stmt)).scalars().all())

    async def get_lab(self, lab_id: int) -> Lab:
        lab = (
            await self.db.execute(
                select(Lab).options(selectinload(Lab.markers)).where(Lab.id == lab_id)
            )
        ).scalar_one_or_none()
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
        self.db.add(lab)
        await self.db.flush()

        for marker_data in data.markers:
            await self._insert_marker(lab.id, marker_data)

        await self.db.commit()
        await self.db.refresh(lab)
        return lab

    async def update_lab(self, lab_id: int, data: LabUpdate) -> Lab:
        lab = await self.get_lab(lab_id)
        patch = data.model_dump(exclude_unset=True)
        markers_patch = patch.pop("markers", None)

        for field, value in patch.items():
            setattr(lab, field, value)

        if markers_patch is not None:
            # Replace-all strategy: delete existing, re-insert.
            for existing in list(lab.markers):
                await self.db.delete(existing)
            await self.db.flush()
            for marker_data in markers_patch:
                if isinstance(marker_data, dict):
                    marker_data = LabMarkerCreate(**marker_data)
                await self._insert_marker(lab.id, marker_data)

        lab.updated_at = datetime.datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(lab)
        return lab

    async def delete_lab(self, lab_id: int) -> None:
        lab = await self.get_lab(lab_id)
        await self.db.delete(lab)
        await self.db.commit()

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
        self.db.add(marker)
        await self.db.flush()

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
                if _ABNORMAL_REF_RE.search(ref_text) or _ABNORMAL_REF_RE.search(
                    value_text
                ):
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
