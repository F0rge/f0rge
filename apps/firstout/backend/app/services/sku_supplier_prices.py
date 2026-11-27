"""A SKU's supplier price rows: read with cost masking, replace all at once.

Reorder reads the preferred supplier's row (``min_order_qty``, ``pack_multiple``).
"""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.sku import SkuCRUD
from app.exceptions import ForbiddenError
from app.models.sku import Sku
from app.models.sku_supplier_price import SkuSupplierPrice
from app.models.supplier import Supplier
from app.permissions import STOCK_COST_VIEW
from app.schemas.sku_overview import SkuSupplierPriceResponse, SkuSupplierPricesReplace
from app.services.permissions import PermissionService
from app.services.skus import field_errors
from f0rge_core.exceptions import ConflictError, NotFoundError
from f0rge_db.crud import unit_of_work
from f0rge_db.organisation import tenant_id_ctx

_PRICE_FIELDS = ("latest_price", "fixed_price")


class SkuSupplierPriceService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.sku_crud = SkuCRUD(db)

    async def list(
        self, sku_id: uuid.UUID, user_id: Optional[uuid.UUID]
    ) -> list[SkuSupplierPriceResponse]:
        sku = await self._sku(sku_id)
        return await self.rows_for(sku, sees_cost=await self._sees_cost(user_id))

    async def rows_for(self, sku: Sku, *, sees_cost: bool) -> list[SkuSupplierPriceResponse]:
        rows = await self.db.execute(
            select(SkuSupplierPrice, Supplier)
            .join(Supplier, Supplier.id == SkuSupplierPrice.supplier_id)
            .where(
                SkuSupplierPrice.team_id == tenant_id_ctx.get(),
                SkuSupplierPrice.sku_id == sku.id,
            )
        )
        result = [
            SkuSupplierPriceResponse(
                id=price.id,
                supplier_id=price.supplier_id,
                supplier_name=supplier.name,
                supplier_is_archived=supplier.is_archived,
                is_preferred=price.supplier_id == sku.preferred_supplier_id,
                supplier_sku=price.supplier_sku,
                latest_price=price.latest_price if sees_cost else None,
                fixed_price=price.fixed_price if sees_cost else None,
                min_order_qty=price.min_order_qty,
                pack_multiple=price.pack_multiple,
                updated_at=price.updated_at,
            )
            for price, supplier in rows
        ]
        result.sort(key=lambda row: (not row.is_preferred, row.supplier_name.casefold()))
        return result

    async def replace(
        self, sku_id: uuid.UUID, data: SkuSupplierPricesReplace, user_id: uuid.UUID
    ) -> list[SkuSupplierPriceResponse]:
        from app.services.sku_archive import SkuArchiveService

        await SkuArchiveService(self.db).lock_skus([sku_id])
        sku = await self._sku(sku_id)
        if sku.is_archived:
            raise ConflictError("Restore the SKU before editing it")
        sees_cost = await self._sees_cost(user_id)

        supplier_ids = [row.supplier_id for row in data.rows]
        errors: list[tuple[str, str]] = []
        if len(set(supplier_ids)) != len(supplier_ids):
            errors.append(("rows", "A supplier is listed more than once"))
        suppliers = {
            supplier.id: supplier
            for supplier in await self.db.scalars(
                select(Supplier).where(
                    Supplier.team_id == tenant_id_ctx.get(), Supplier.id.in_(supplier_ids)
                )
            )
        }
        existing = {
            price.supplier_id: price
            for price in await self.db.scalars(
                select(SkuSupplierPrice).where(
                    SkuSupplierPrice.team_id == tenant_id_ctx.get(),
                    SkuSupplierPrice.sku_id == sku.id,
                )
            )
        }
        for index, row in enumerate(data.rows):
            supplier = suppliers.get(row.supplier_id)
            if supplier is None:
                errors.append((f"rows.{index}.supplier_id", "Supplier not found"))
            elif supplier.is_archived and row.supplier_id not in existing:
                errors.append(
                    (f"rows.{index}.supplier_id", f"Supplier '{supplier.name}' is archived")
                )
        if errors:
            raise field_errors(errors)

        if not sees_cost:
            # Prices stay as stored. Sending one, or removing a priced row, changes them.
            changes_price = any(
                getattr(row, field) is not None for row in data.rows for field in _PRICE_FIELDS
            ) or any(
                price.latest_price is not None or price.fixed_price is not None
                for supplier_id, price in existing.items()
                if supplier_id not in supplier_ids
            )
            if changes_price:
                raise ForbiddenError("Changing supplier prices needs stock.cost.view")

        async with unit_of_work(self.db):
            for supplier_id, price in existing.items():
                if supplier_id not in supplier_ids:
                    await self.db.delete(price)
            for row in data.rows:
                price = existing.get(row.supplier_id)
                if price is None:
                    price = SkuSupplierPrice(sku_id=sku.id, supplier_id=row.supplier_id)
                    self.db.add(price)
                price.supplier_sku = row.supplier_sku
                price.min_order_qty = row.min_order_qty
                price.pack_multiple = row.pack_multiple
                if sees_cost:
                    price.latest_price = row.latest_price
                    price.fixed_price = row.fixed_price
            await self.db.flush()
        return await self.rows_for(sku, sees_cost=sees_cost)

    async def _sku(self, sku_id: uuid.UUID) -> Sku:
        sku = await self.sku_crud.get_by_id(sku_id)
        if sku is None:
            raise NotFoundError("SKU not found")
        return sku

    async def _sees_cost(self, user_id: Optional[uuid.UUID]) -> bool:
        if user_id is None:
            return False
        return await PermissionService(self.db).has_permission(user_id, STOCK_COST_VIEW)
