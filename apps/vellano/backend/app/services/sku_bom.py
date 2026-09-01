from __future__ import annotations

import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.sku import SkuCRUD
from app.crud.sku_bom_line import SkuBomLineCRUD
from app.models.sku_bom_line import SkuBomLine
from app.schemas.sku_bom import SkuBomLineResponse, SkuBomReplace
from f0rge_core.exceptions import ConflictError, NotFoundError, ValidationError
from f0rge_db.crud import unit_of_work


class SkuBomService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = SkuBomLineCRUD(db)
        self.sku_crud = SkuCRUD(db)

    async def list(self, parent_sku_id: uuid.UUID) -> list[SkuBomLineResponse]:
        await self._get_sku_or_404(parent_sku_id)
        rows = await self.crud.list_by_parent(parent_sku_id)
        return [SkuBomLineResponse.model_validate(row) for row in rows]

    async def replace(
        self,
        parent_sku_id: uuid.UUID,
        data: SkuBomReplace,
    ) -> list[SkuBomLineResponse]:
        await self._get_sku_or_404(parent_sku_id)
        seen: set[uuid.UUID] = set()
        prepared: list[tuple[uuid.UUID, int]] = []
        for line in data.lines:
            if line.component_sku_id == parent_sku_id:
                raise ValidationError("BOM cannot include the parent SKU as a component")
            if line.component_sku_id in seen:
                raise ValidationError("Duplicate component SKU in BOM")
            component = await self.sku_crud.get_by_id(line.component_sku_id)
            if component is None:
                raise NotFoundError("SKU not found")
            seen.add(line.component_sku_id)
            prepared.append((line.component_sku_id, line.qty))

        created: list[SkuBomLine] = []
        try:
            async with unit_of_work(self.db):
                await self.crud.delete_for_parent(parent_sku_id)
                for component_sku_id, qty in prepared:
                    row = SkuBomLine(
                        parent_sku_id=parent_sku_id,
                        component_sku_id=component_sku_id,
                        qty=qty,
                    )
                    await self.crud.add_and_flush(row)
                    created.append(row)
        except IntegrityError as exc:
            raise ConflictError("A BOM line for this component already exists") from exc

        return [SkuBomLineResponse.model_validate(row) for row in created]

    async def _get_sku_or_404(self, sku_id: uuid.UUID) -> None:
        sku = await self.sku_crud.get_by_id(sku_id)
        if sku is None:
            raise NotFoundError("SKU not found")
