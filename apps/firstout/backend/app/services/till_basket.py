from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Any, Iterable, NoReturn, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.till_basket import TillBasketCRUD
from app.exceptions import BasketExpiredSignal, TillBasketConflictError
from app.models.sku import Sku
from app.models.sku_bom_line import SkuBomLine
from app.models.stock_reservation import HOLDER_BASKET
from app.models.till_basket import TillBasket as TillBasketRow
from app.schemas.held_sale import TillBasket, TillBasketUpdate
from app.schemas.till_reservation import BlockingReservation, TillReservation
from app.services.held_sale import HeldSaleService, clock as _clock, kept_quantities
from app.services.stock_availability import StockAvailability, StockUnavailable
from f0rge_core.exceptions import NotFoundError, ValidationError
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


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


class TillBasketService:
    """The caller's open basket: one per user per showroom, replaced whole.

    Lines reserve stock company-wide. Every write goes through ``set_contents`` so
    the basket, its expiry and its reservations can never disagree.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = TillBasketCRUD(db)
        self.held = HeldSaleService(db)
        self.availability = StockAvailability(db)

    async def get_or_create(self, location_id: uuid.UUID, user_id: uuid.UUID) -> TillBasket:
        async with unit_of_work(self.db):
            self.held.require_active(await self.held.showroom(location_id))
            await self.crud.ensure(user_id, location_id)
            row = await self.crud.owned(user_id, location_id=location_id, lock=True)
            assert row is not None
            now = _now()
            if self._due(row, now):
                await self._expire(row)
            return self.response(row)

    async def reservations(
        self, location_id: uuid.UUID, user_id: uuid.UUID
    ) -> list[TillReservation]:
        """Stock reserved by baskets other than the caller's own at this showroom."""
        self.held.require_active(await self.held.showroom(location_id))
        own = await self.crud.owned(user_id, location_id=location_id)
        rows = await self.availability.others_at_till(_now(), own.id if own else None)
        return [TillReservation.model_validate(row) for row in rows]

    async def get_owned(
        self, basket_id: uuid.UUID, user_id: uuid.UUID, *, lock: bool = False
    ) -> TillBasketRow:
        row = await self.crud.owned(user_id, basket_id=basket_id, lock=lock)
        if row is None:
            raise NotFoundError("Basket not found")
        return row

    async def lock_live(
        self,
        basket_id: uuid.UUID,
        user_id: uuid.UUID,
        location_id: uuid.UUID,
        now: datetime.datetime,
    ) -> TillBasketRow:
        """Lock the caller's basket for a sale, hold or resume.

        ``now`` is the request's start, taken before waiting on the row lock. A basket
        due at that moment raises ``BasketExpiredSignal`` without writing; the caller
        rolls back and passes it to ``refuse_expired`` in a fresh transaction.
        """
        row = await self.get_owned(basket_id, user_id, lock=True)
        if row.location_id != location_id:
            raise ValidationError("The basket belongs to a different showroom")
        if self._due(row, now):
            raise BasketExpiredSignal(row.id, user_id, row.expires_at)
        return row

    async def refuse_expired(self, signal: BasketExpiredSignal) -> NoReturn:
        """Empty the basket in a fresh transaction, then refuse with ``basket_expired``."""
        async with unit_of_work(self.db):
            row = await self.get_owned(signal.basket_id, signal.user_id, lock=True)
            if row.lines and row.expires_at == signal.expires_at:
                error = await self._expire_and_describe(row)
            else:
                error = TillBasketConflictError(
                    "basket_changed",
                    "The basket changed. Review it before continuing.",
                    self.response(row).model_dump(mode="json"),
                )
        raise error

    async def _expire_and_describe(self, row: TillBasketRow) -> TillBasketConflictError:
        message = f"This sale expired at {_clock(row.expires_at)}. Add the items again."
        await self._expire(row)
        return TillBasketConflictError(
            "basket_expired", message, self.response(row).model_dump(mode="json")
        )

    async def replace(
        self, basket_id: uuid.UUID, data: TillBasketUpdate, user_id: uuid.UUID
    ) -> TillBasket:
        expired: Optional[TillBasketConflictError] = None
        async with unit_of_work(self.db):
            row = await self.get_owned(basket_id, user_id, lock=True)
            now = _now()
            if self._due(row, now):
                expired = await self._expire_and_describe(row)
            else:
                if row.last_operation_id == data.operation_id:
                    return self.response(row)
                if row.version != data.version:
                    raise TillBasketConflictError(
                        "basket_version_conflict",
                        "The basket changed. Reload it before editing.",
                        self.response(row).model_dump(mode="json"),
                    )
                await self.prune(now)
                self.held.require_active(await self.held.showroom(row.location_id, lock=True))
                await self.held.validate_cart(data)
                # A line resumed from a held sale keeps its held quantity while it stays.
                kept = kept_quantities(row)
                await self.set_contents(
                    row,
                    customer_id=data.customer_id,
                    note=data.note,
                    note_printed=data.note_printed,
                    note_internal=data.note_internal,
                    sales_staff_id=data.sales_staff_id,
                    quote_id=data.quote_id,
                    pick_id=data.pick_id,
                    linked_pick_ids=data.linked_pick_ids,
                    lines=[
                        {**line.model_dump(mode="json"), "kept_qty": kept.get(str(line.sku_id))}
                        for line in data.lines
                    ],
                    operation_id=data.operation_id,
                )
                return self.response(row)
        assert expired is not None
        raise expired

    async def prune(self, now: datetime.datetime) -> None:
        """Drop the tenant's expired reservations, held sales and baskets."""
        await self.availability.prune(now)
        await self.held.prune_expired(now)
        await self.crud.empty_expired(now)

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

    async def set_contents(
        self,
        row: TillBasketRow,
        *,
        customer_id: Optional[uuid.UUID] = None,
        note: Optional[str] = None,
        note_printed: Optional[str] = None,
        note_internal: Optional[str] = None,
        sales_staff_id: Optional[uuid.UUID] = None,
        quote_id: Optional[uuid.UUID] = None,
        pick_id: Optional[uuid.UUID] = None,
        linked_pick_ids: Optional[dict[Any, Any]] = None,
        lines: Optional[list[dict]] = None,
        operation_id: Optional[uuid.UUID] = None,
    ) -> None:
        """The one way to change a basket: contents, expiry clock and reservations together.

        Reservations are synced first, so a refused reservation leaves the basket untouched.
        No lines empties it, clears its expiry and releases everything it reserved.
        """
        now = _now()
        stored = [
            {
                "sku_id": str(line["sku_id"]),
                "qty": line["qty"],
                "discount_percent": str(line["discount_percent"]),
                # A held quantity kept against the sale quantity rule (never from a client).
                **({"kept_qty": int(line["kept_qty"])} if line.get("kept_qty") else {}),
            }
            for line in (lines or [])
        ]
        expires_at = now + await self.availability.hold_time() if stored else None
        try:
            await self.availability.reserve(
                (HOLDER_BASKET, row.id),
                row.location_id,
                await self._reservable(stored),
                expires_at,
                now,
            )
        except StockUnavailable as exc:
            where = ""
            blocking = None
            if exc.blocking:
                blocking = BlockingReservation(**exc.blocking).model_dump(mode="json")
                kind = {"basket": "in an open sale", "held_sale": "in a held sale"}.get(
                    blocking["holder_kind"], "for an invoice"
                )
                where = f" Reserved {kind} at {blocking['location_name']}."
            raise TillBasketConflictError(
                "stock_reserved",
                f"Only {exc.available} available.{where}",
                self.response(row).model_dump(mode="json"),
                sku_id=str(exc.sku_id),
                available=exc.available,
                blocking=blocking,
            ) from exc
        row.customer_id = customer_id
        row.note = note
        row.note_printed = note_printed
        row.note_internal = note_internal
        row.sales_staff_id = sales_staff_id
        row.quote_id = quote_id
        row.pick_id = pick_id
        row.linked_pick_ids = {str(k): str(v) for k, v in (linked_pick_ids or {}).items()}
        row.lines = stored
        row.last_operation_id = operation_id
        row.version += 1
        row.updated_at = now
        row.expires_at = expires_at
        row.expired_at = None

    @staticmethod
    def _due(row: TillBasketRow, now: datetime.datetime) -> bool:
        return bool(row.lines) and row.expires_at is not None and row.expires_at <= now

    async def _expire(self, row: TillBasketRow) -> None:
        """Lazy expiry: empty the basket and free its stock, remembering when it lapsed."""
        lapsed = row.expires_at
        await self.set_contents(row)
        row.expired_at = lapsed

    async def _reservable(self, lines: list[dict]) -> dict[uuid.UUID, int]:
        """Qty per SKU to reserve; kits and no-stock-needed SKUs keep their own rules."""
        wanted: dict[uuid.UUID, int] = {}
        for line in lines:
            sku_id = uuid.UUID(line["sku_id"])
            wanted[sku_id] = wanted.get(sku_id, 0) + int(line["qty"])
        if not wanted:
            return wanted
        exempt = set(
            await self.db.scalars(
                select(Sku.id).where(Sku.id.in_(wanted), Sku.till_no_stock_required.is_(True))
            )
        )
        exempt |= set(
            await self.db.scalars(
                select(SkuBomLine.parent_sku_id).where(SkuBomLine.parent_sku_id.in_(wanted))
            )
        )
        return {sku: qty for sku, qty in wanted.items() if sku not in exempt}

    @staticmethod
    def response(row: TillBasketRow) -> TillBasket:
        return TillBasket.model_validate(row, from_attributes=True)
