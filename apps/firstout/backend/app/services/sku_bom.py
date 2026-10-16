from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Union

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.sku import SkuCRUD
from app.crud.sku_bom_line import SkuBomLineCRUD
from app.models.sku_bom_line import SkuBomLine
from app.schemas.sku_bom import SkuBomLineResponse, SkuBomReplace
from f0rge_core.exceptions import ConflictError, NotFoundError, ValidationError
from f0rge_db.crud import unit_of_work


def whole_component_qty(bom_qty: Union[Decimal, int], kit_qty: int) -> int:
    """Component units for ``kit_qty`` kits. Stock is counted in whole units.

    Cin7 assemblies can carry fractional components (for example 0.5 m of fabric).
    They are stored as-is, but picking or selling such a kit from stock would need
    fractional on-hand, so it is refused instead of silently rounded.
    """
    need = Decimal(bom_qty) * kit_qty
    if need != need.to_integral_value():
        raise ValidationError(
            "Kit has a fractional component quantity and cannot be picked or sold from stock"
        )
    return int(need)


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
        prepared: list[tuple[uuid.UUID, Decimal]] = []
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
