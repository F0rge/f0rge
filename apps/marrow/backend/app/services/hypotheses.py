from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.hypotheses import HypothesisCRUD
from app.models.hypothesis import HYPOTHESIS_STATUSES, Hypothesis
from app.schemas.hypothesis import HypothesisCreate, HypothesisUpdate
from f0rge_core.exceptions import ConflictError, NotFoundError, ValidationError
from f0rge_db.tenant import current_user_id


class HypothesisService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = HypothesisCRUD(db)

    async def list(self, status: Optional[str] = None) -> list[Hypothesis]:
        if status is not None and status not in HYPOTHESIS_STATUSES:
            raise ValidationError("status must be live, weakening, killed, or parked.")
        return await self.crud.list(status)

    async def get(self, hypothesis_id: uuid.UUID) -> Hypothesis:
        row = await self.crud.get_by_id(hypothesis_id)
        if row is None:
            raise NotFoundError("Hypothesis not found.")
        return row

    async def get_by_slug(self, slug: str) -> Hypothesis:
        row = await self.crud.get_by_slug(slug)
        if row is None:
            raise NotFoundError("Hypothesis not found.")
        return row

    async def create(self, data: HypothesisCreate) -> Hypothesis:
        existing = await self.crud.get_by_slug(data.slug)
        if existing is not None:
            raise ConflictError(f"Hypothesis slug '{data.slug}' already exists.")
        row = Hypothesis(
            user_id=current_user_id(),
            slug=data.slug,
            title=data.title,
            status=data.status,
            layer=data.layer,
            kill_test=data.kill_test,
            next_move=data.next_move,
            last_evidence=data.last_evidence,
            cite=data.cite,
            sort_order=data.sort_order,
        )
        self.crud.add(row)
        return await self.crud.commit_refresh(row)

    async def update(self, hypothesis_id: uuid.UUID, data: HypothesisUpdate) -> Hypothesis:
        row = await self.get(hypothesis_id)
        patch = data.model_dump(exclude_unset=True)
        new_slug = patch.get("slug")
        if new_slug is not None and new_slug != row.slug:
            clash = await self.crud.get_by_slug(new_slug)
            if clash is not None:
                raise ConflictError(f"Hypothesis slug '{new_slug}' already exists.")
        for field, value in patch.items():
            setattr(row, field, value)
        return await self.crud.commit_refresh(row)
