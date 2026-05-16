from __future__ import annotations

import datetime
import re
from typing import List, Optional

from sqlalchemy.orm import Session, selectinload

from app.exceptions import NotFoundError, ValidationError
from app.models.lab import Lab
from app.models.lab_marker import LabMarker
from app.schemas.lab import LabCreate, LabUpdate, LabMarkerCreate

_ABNORMAL_REF_RE = re.compile(
    r"\b(positive|elevated|reactive|abnormal|class\s*[>=]\s*\d|high|present)\b",
    re.IGNORECASE,
)


class LabsService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_labs(
        self,
        start_date: Optional[datetime.date] = None,
        end_date: Optional[datetime.date] = None,
        lab_type: Optional[str] = None,
    ) -> List[Lab]:
        query = self.db.query(Lab).options(selectinload(Lab.markers))
        if start_date is not None:
            query = query.filter(Lab.lab_date >= start_date)
        if end_date is not None:
            query = query.filter(Lab.lab_date <= end_date)
        if lab_type is not None:
            query = query.filter(Lab.type == lab_type)
        return query.order_by(Lab.lab_date.desc()).all()

    def get_lab(self, lab_id: int) -> Lab:
        lab = (
            self.db.query(Lab)
            .options(selectinload(Lab.markers))
            .filter(Lab.id == lab_id)
            .first()
        )
        if lab is None:
            raise NotFoundError("Lab not found.")
        return lab

    def create_lab(
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
        self.db.flush()

        for marker_data in data.markers:
            self._insert_marker(lab.id, marker_data)

        self.db.commit()
        self.db.refresh(lab)
        return lab

    def update_lab(self, lab_id: int, data: LabUpdate) -> Lab:
        lab = self.get_lab(lab_id)
        patch = data.model_dump(exclude_unset=True)
        markers_patch = patch.pop("markers", None)

        for field, value in patch.items():
            setattr(lab, field, value)

        if markers_patch is not None:
            # Replace-all strategy: delete existing, re-insert.
            for existing in list(lab.markers):
                self.db.delete(existing)
            self.db.flush()
            for marker_data in markers_patch:
                if isinstance(marker_data, dict):
                    marker_data = LabMarkerCreate(**marker_data)
                self._insert_marker(lab.id, marker_data)

        lab.updated_at = datetime.datetime.utcnow()
        self.db.commit()
        self.db.refresh(lab)
        return lab

    def delete_lab(self, lab_id: int) -> None:
        lab = self.get_lab(lab_id)
        self.db.delete(lab)
        self.db.commit()

    def _insert_marker(self, lab_id: int, data: LabMarkerCreate) -> None:
        catalog_id = data.catalog_id
        canonical_name = data.canonical_name

        if not catalog_id:
            # Lazy import to avoid circular dependency.
            from app.services.lab_catalog import LabMarkerCatalogService

            if not canonical_name and not data.display_name:
                raise ValidationError(
                    "Marker requires canonical_name or display_name."
                )
            lookup_name = canonical_name or data.display_name
            catalog_entry = LabMarkerCatalogService(self.db).resolve_or_create(
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
        self.db.flush()

    @staticmethod
    def compute_flag(
        value: Optional[float],
        value_text: Optional[str],
        ref_low: Optional[float],
        ref_high: Optional[float],
        ref_text: Optional[str],
    ) -> str:
        """Compute the clinical flag for a marker reading.

        Decision order:
        1. No numeric value → "unknown".
        2. Both ref bounds present → low / normal / high.
        3. Only one ref bound → compare, else normal.
        4. No numeric refs but ref_text looks abnormal and value_text matches → abnormal.
        5. Default → "unknown".
        """
        if value is None:
            # Text-only row: check ref_text for "abnormal-like" language.
            if ref_text and value_text:
                if _ABNORMAL_REF_RE.search(ref_text) or _ABNORMAL_REF_RE.search(
                    value_text
                ):
                    return "abnormal"
            return "unknown"

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
