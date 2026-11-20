from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Any, Iterable, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.till_basket import TillBasketCRUD
from app.exceptions import TillBasketConflictError
from app.models.till_basket import TillBasket as TillBasketRow
from app.schemas.held_sale import TillBasket, TillBasketUpdate
from app.services.held_sale import HeldSaleService
from f0rge_core.exceptions import NotFoundError
from f0rge_db.crud import unit_of_work


def line_key(sku_id: Any, qty: Any, discount: Any) -> tuple[str, int, Decimal]:
    return (str(sku_id), int(qty), Decimal(str(discount)))


def line_keys(lines: Iterable[Any]) -> list[tuple[str, int, Decimal]]:
    """Order-free fingerprint of lines given as dicts or objects."""
    keys = [
        line_key(*(line[k] for k in ("sku_id", "qty", "discount_percent")))
        if isinstance(line, dict)
        else line_key(line.sku_id, line.qty, line.discount_percent)
        for line in lines
    ]
    return sorted(keys)


class TillBasketService:
    """The caller's open basket: one per user per showroom, replaced whole."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = TillBasketCRUD(db)
        self.held = HeldSaleService(db)

    async def get_or_create(self, location_id: uuid.UUID, user_id: uuid.UUID) -> TillBasket:
        async with unit_of_work(self.db):
            self.held._require_active(await self.held._showroom(location_id))
            await self.crud.ensure(user_id, location_id)
            row = await self.crud.owned(user_id, location_id=location_id)
            assert row is not None
            return self.response(row)

    async def get_owned(
        self, basket_id: uuid.UUID, user_id: uuid.UUID, *, lock: bool = False
    ) -> TillBasketRow:
        row = await self.crud.owned(user_id, basket_id=basket_id, lock=lock)
        if row is None:
            raise NotFoundError("Basket not found")
        return row

    async def replace(
        self, basket_id: uuid.UUID, data: TillBasketUpdate, user_id: uuid.UUID
    ) -> TillBasket:
        async with unit_of_work(self.db):
            row = await self.get_owned(basket_id, user_id, lock=True)
            if row.last_operation_id == data.operation_id:
                return self.response(row)
            if row.version != data.version:
                raise TillBasketConflictError(
                    "basket_version_conflict",
                    "The basket changed. Reload it before editing.",
                    self.response(row).model_dump(mode="json"),
                )
            self.held._require_active(await self.held._showroom(row.location_id, lock=True))
            await self.held._validate_cart(data)
            self.set_contents(
                row,
                customer_id=data.customer_id,
                note=data.note,
                pick_id=data.pick_id,
                linked_pick_ids=data.linked_pick_ids,
                lines=[line.model_dump(mode="json") for line in data.lines],
                operation_id=data.operation_id,
            )
            return self.response(row)

    def assert_matches(self, row: TillBasketRow, lines: Iterable[Any], version: Optional[int]):
        """The basket must still hold exactly what is being sold or held."""
        if (version is not None and row.version != version) or line_keys(row.lines) != line_keys(
            lines
        ):
            raise TillBasketConflictError(
                "basket_changed",
                "The basket changed. Review it before continuing.",
                self.response(row).model_dump(mode="json"),
            )

    @staticmethod
    def set_contents(
        row: TillBasketRow,
        *,
        customer_id: Optional[uuid.UUID] = None,
        note: Optional[str] = None,
        pick_id: Optional[uuid.UUID] = None,
        linked_pick_ids: Optional[dict[Any, Any]] = None,
        lines: Optional[list[dict]] = None,
        operation_id: Optional[uuid.UUID] = None,
    ) -> None:
        row.customer_id = customer_id
        row.note = note
        row.pick_id = pick_id
        row.linked_pick_ids = {str(k): str(v) for k, v in (linked_pick_ids or {}).items()}
        row.lines = [
            {
                "sku_id": str(line["sku_id"]),
                "qty": line["qty"],
                "discount_percent": str(line["discount_percent"]),
            }
            for line in (lines or [])
        ]
        row.last_operation_id = operation_id
        row.version += 1
        row.updated_at = datetime.datetime.now(datetime.timezone.utc)

    @staticmethod
    def response(row: TillBasketRow) -> TillBasket:
        return TillBasket.model_validate(row, from_attributes=True)
