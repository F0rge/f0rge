from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Any, Iterable, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.till_basket import TillBasketCRUD
from app.exceptions import TillBasketConflictError
from app.models.sku import Sku
from app.models.sku_bom_line import SkuBomLine
from app.models.stock_reservation import HOLDER_BASKET
from app.models.team_settings import DEFAULT_TILL_HOLD_HOURS, TeamSettings
from app.models.till_basket import TillBasket as TillBasketRow
from app.schemas.held_sale import TillBasket, TillBasketUpdate
from app.schemas.till_reservation import BlockingReservation, TillReservation
from app.services.held_sale import HeldSaleService
from app.services.stock_availability import StockAvailability, StockUnavailable
from f0rge_core.exceptions import NotFoundError, ValidationError
from f0rge_db.crud import unit_of_work
from f0rge_db.organisation import tenant_id_ctx

# South Africa has no daylight saving, so a fixed offset is exact.
_SAST = datetime.timezone(datetime.timedelta(hours=2))


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


def _clock(moment: datetime.datetime) -> str:
    return moment.astimezone(_SAST).strftime("%H:%M")


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
            self.held._require_active(await self.held._showroom(location_id))
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
        self.held._require_active(await self.held._showroom(location_id))
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
        self, basket_id: uuid.UUID, user_id: uuid.UUID, location_id: uuid.UUID
    ) -> TillBasketRow:
        """Lock the caller's basket for a sale, hold or resume.

        One that expired before this request is emptied and the emptying committed,
        then refused; the caller must add its items again.
        """
        row = await self.get_owned(basket_id, user_id, lock=True)
        if row.location_id != location_id:
            raise ValidationError("The basket belongs to a different showroom")
        if self._due(row, _now()):
            async with unit_of_work(self.db):
                message = f"This sale expired at {_clock(row.expires_at)}. Add the items again."
                await self._expire(row)
                payload = self.response(row).model_dump(mode="json")
            raise TillBasketConflictError("basket_expired", message, payload)
        return row

    async def replace(
        self, basket_id: uuid.UUID, data: TillBasketUpdate, user_id: uuid.UUID
    ) -> TillBasket:
        expired: Optional[dict] = None
        message = ""
        async with unit_of_work(self.db):
            row = await self.get_owned(basket_id, user_id, lock=True)
            now = _now()
            if self._due(row, now):
                message = f"This sale expired at {_clock(row.expires_at)}. Add the items again."
                await self._expire(row)
                expired = self.response(row).model_dump(mode="json")
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
                self.held._require_active(await self.held._showroom(row.location_id, lock=True))
                await self.held._validate_cart(data)
                await self.set_contents(
                    row,
                    customer_id=data.customer_id,
                    note=data.note,
                    pick_id=data.pick_id,
                    linked_pick_ids=data.linked_pick_ids,
                    lines=[line.model_dump(mode="json") for line in data.lines],
                    operation_id=data.operation_id,
                )
                return self.response(row)
        raise TillBasketConflictError("basket_expired", message, expired)

    async def prune(self, now: datetime.datetime) -> None:
        """Drop the tenant's expired reservations and empty its expired baskets."""
        await self.availability.prune(now)
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
            }
            for line in (lines or [])
        ]
        expires_at = now + await self._hold_time() if stored else None
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

    async def _hold_time(self) -> datetime.timedelta:
        hours = await self.db.scalar(
            select(TeamSettings.till_hold_hours).where(TeamSettings.team_id == tenant_id_ctx.get())
        )
        return datetime.timedelta(hours=hours or DEFAULT_TILL_HOLD_HOURS)

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
