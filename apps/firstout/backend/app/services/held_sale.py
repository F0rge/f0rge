from __future__ import annotations

import datetime
import uuid
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.held_sale import HeldSaleCRUD
from app.crud.user import UserCRUD
from app.exceptions import HeldResumeTargetChangedError
from app.models.customer import Customer
from app.models.held_sale import HeldSale as HeldSaleRow
from app.models.held_sale_operation import HeldSaleOperation
from app.models.location import Location
from app.models.pick import Pick, PickSourceType, PickStatus
from app.models.sku import Sku
from app.schemas.held_sale import (
    HeldSale,
    HeldSaleCreate,
    HeldSaleDelete,
    HeldSaleDeleteResult,
    HeldSaleLine,
    HeldSaleNoteUpdate,
    HeldSaleResume,
    HeldSaleResumeResult,
)
from app.schemas.till import TillSaleLineCreate
from app.services.party_archive import assert_customer_active
from app.services.record_workspace_filters import payload_hash
from app.services.sellability import assert_sku_sellable
from app.services.till_pricing import TillPricing
from app.services.till_seed import WALK_IN_CUSTOMER_NAME
from f0rge_core.exceptions import ConflictError, NotFoundError, ValidationError
from f0rge_db.crud import unit_of_work

_RECEIPT_TTL = datetime.timedelta(days=30)
_PICK_COMMITMENT_STATUSES = (PickStatus.CONFIRMED, PickStatus.PICKING, PickStatus.STAGED)


class HeldSaleService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = HeldSaleCRUD(db)

    async def list(self, location_id: uuid.UUID) -> list[HeldSale]:
        self._require_active(await self._showroom(location_id))
        return [self._response(row) for row in await self.crud.list(location_id)]

    async def create(self, data: HeldSaleCreate, actor_id: uuid.UUID) -> HeldSale:
        try:
            async with unit_of_work(self.db):
                showroom = await self._showroom(data.location_id, lock=True)
                now = datetime.datetime.now(datetime.timezone.utc)
                await self.crud.prune_operations(showroom.id, now)
                baskets = basket = None
                # A retried hold must not wipe a basket the cashier refilled since.
                if data.basket_id is not None and await self.crud.get(showroom.id, data.id) is None:
                    baskets, basket = await self._owned_basket(
                        data.basket_id, actor_id, data.location_id
                    )
                    baskets.assert_matches(basket, data.lines, None)
                if data.basket_id is not None:
                    await self._prune_baskets(now)
                row = await self._save(data, actor_id, showroom, now)
                if baskets is not None and basket is not None:
                    # Held sales reserve nothing yet: emptying releases the basket's stock.
                    await baskets.set_contents(basket)
                return self._response(row)
        except IntegrityError as exc:
            if getattr(exc.orig, "sqlstate", None) != "23505":
                raise
            raise ConflictError("This held-sale ID is already in use") from exc

    async def edit_note(self, held_id: uuid.UUID, data: HeldSaleNoteUpdate) -> HeldSale:
        async with unit_of_work(self.db):
            self._require_active(await self._showroom(data.location_id, lock=True))
            row = await self.crud.get(data.location_id, held_id)
            if row is None:
                raise NotFoundError("Held sale not found in this showroom")
            note = (data.note or "").strip() or None
            if note != row.note:
                if row.version != data.version:
                    raise ConflictError("The held sale changed. Refresh the list before editing.")
                row.note = note
                row.version += 1
            return self._response(row)

    async def resume(
        self, held_id: uuid.UUID, data: HeldSaleResume, actor_id: uuid.UUID
    ) -> HeldSaleResumeResult:
        try:
            async with unit_of_work(self.db):
                showroom = await self._showroom(data.location_id, lock=True)
                now = datetime.datetime.now(datetime.timezone.utc)
                await self.crud.prune_operations(showroom.id, now)
                fingerprint = payload_hash(
                    {"held_id": str(held_id), "request": data.model_dump(mode="json")}
                )
                replay = await self.crud.operation(
                    showroom.id, actor_id, "resume", data.operation_id, now
                )
                if replay is not None:
                    self._require_matching_request(replay, fingerprint)
                    current_basket = None
                    if data.basket_id is not None:
                        baskets, basket = await self._owned_basket(
                            data.basket_id, actor_id, data.location_id, refuse_expired=False
                        )
                        current_basket = baskets.response(basket)
                    return HeldSaleResumeResult(
                        resumed_id=replay.held_sale_id,
                        held_current_id=replay.held_current_id,
                        **({"basket": current_basket} if current_basket else {}),
                    )
                self._require_active(showroom)
                row = await self.crud.get(showroom.id, held_id)
                if row is None:
                    raise HeldResumeTargetChangedError(
                        "This sale is no longer held in this showroom"
                    )
                if row.version != data.version:
                    raise HeldResumeTargetChangedError(
                        "The held sale changed. Refresh the list before resuming."
                    )
                await self._validate_cart(
                    HeldSaleCreate(
                        id=row.id,
                        location_id=row.location_id,
                        customer_id=row.customer_id,
                        lines=[
                            {
                                "sku_id": line["sku_id"],
                                "qty": line["qty"],
                                "discount_percent": line["discount_percent"],
                            }
                            for line in row.lines
                        ],
                        pick_id=row.pick_id,
                        linked_pick_ids=row.linked_pick_ids,
                    )
                )
                if data.current is not None and data.current.id == row.id:
                    raise ValidationError("The current basket needs a different held-sale ID")
                baskets = basket = None
                if data.basket_id is not None:
                    baskets, basket = await self._owned_basket(
                        data.basket_id, actor_id, data.location_id
                    )

                # Retire the selected basket and save the current basket in
                # the same transaction, so a failed swap leaves both untouched.
                await self.crud.delete(row)
                await self.crud.flush()
                current_id = None
                if data.current is not None:
                    current_id = (await self._save(data.current, actor_id, showroom, now)).id
                loaded = None
                if baskets is not None and basket is not None:
                    # Written through the reserve path: 409 stock_reserved aborts the resume.
                    await baskets.set_contents(
                        basket,
                        customer_id=row.customer_id,
                        note=row.note,
                        pick_id=row.pick_id,
                        linked_pick_ids=row.linked_pick_ids,
                        lines=row.lines,
                        operation_id=data.operation_id,
                    )
                    loaded = baskets.response(basket)
                    await self._prune_baskets(now)
                self._record_operation(
                    showroom.id,
                    actor_id,
                    "resume",
                    data.operation_id,
                    fingerprint,
                    held_id,
                    now,
                    held_current_id=current_id,
                )
                return HeldSaleResumeResult(
                    resumed_id=held_id,
                    held_current_id=current_id,
                    **({"basket": loaded} if loaded else {}),
                )
        except IntegrityError as exc:
            if getattr(exc.orig, "sqlstate", None) != "23505":
                raise
            raise ConflictError("This held-sale ID is already in use") from exc

    async def delete(self, data: HeldSaleDelete) -> HeldSaleDeleteResult:
        async with unit_of_work(self.db):
            showroom = await self._showroom(data.location_id, lock=True)
            self._require_active(showroom)
            actual = await self.crud.ids(showroom.id)
            selected = set(data.ids)
            if (data.all and selected != actual) or not selected <= actual:
                raise ConflictError("Held sales changed. Refresh the list before deleting.")
            if selected:
                await self.crud.delete_sales(showroom.id, selected)
            return HeldSaleDeleteResult(deleted_count=len(selected))

    async def _save(
        self,
        data: HeldSaleCreate,
        actor_id: uuid.UUID,
        showroom: Location,
        now: datetime.datetime,
    ) -> HeldSaleRow:
        fingerprint = payload_hash(data.model_dump(mode="json"))
        replay = await self.crud.operation(showroom.id, actor_id, "save", data.id, now)
        existing = await self.crud.get(showroom.id, data.id)
        if replay is not None:
            self._require_matching_request(replay, fingerprint)
            if existing is None:
                raise ConflictError("This sale is no longer held in this showroom")
            return existing
        self._require_active(showroom)
        if existing is not None:
            raise ConflictError("This held-sale ID is already in use")
        customer, skus = await self._validate_cart(data)
        actor = await UserCRUD(self.db).get_by_id(actor_id)
        if actor is None:
            raise NotFoundError("Staff member not found")
        pricing = None
        if customer is not None:
            try:
                pricing = await TillPricing.for_customer(self.db, customer)
            except (ConflictError, ValidationError):
                pass
        lines: list[HeldSaleLine] = []
        for line in data.lines:
            sku = skus[line.sku_id]
            estimate = None
            if pricing is not None:
                try:
                    priced = await pricing.line(
                        sku,
                        TillSaleLineCreate(
                            sku_id=line.sku_id, qty=line.qty, discount_percent=line.discount_percent
                        ),
                    )
                    estimate = priced.inc_vat
                except (ConflictError, ValidationError):
                    pass
            lines.append(
                HeldSaleLine(
                    **line.model_dump(),
                    sku_code=sku.our_ref,
                    sku_name=sku.name,
                    estimated_total_inc_vat=estimate,
                )
            )
        total = (
            sum(
                line.estimated_total_inc_vat
                for line in lines
                if line.estimated_total_inc_vat is not None
            )
            if all(line.estimated_total_inc_vat is not None for line in lines)
            else None
        )
        row = await self.crud.add_and_flush(
            HeldSaleRow(
                id=data.id,
                location_id=data.location_id,
                customer_id=data.customer_id,
                customer_name=customer.name if customer is not None else WALK_IN_CUSTOMER_NAME,
                held_by_name=actor.display_name or actor.email,
                held_at=now,
                note=data.note,
                estimated_total_inc_vat=total,
                pick_id=data.pick_id,
                linked_pick_ids={str(sku): str(pick) for sku, pick in data.linked_pick_ids.items()},
                lines=[line.model_dump(mode="json") for line in lines],
            )
        )
        self._record_operation(showroom.id, actor_id, "save", data.id, fingerprint, row.id, now)
        return row

    async def _owned_basket(
        self,
        basket_id: uuid.UUID,
        actor_id: uuid.UUID,
        location_id: uuid.UUID,
        *,
        refuse_expired: bool = True,
    ):
        from app.services.till_basket import TillBasketService

        baskets = TillBasketService(self.db)
        if refuse_expired:
            return baskets, await baskets.lock_live(basket_id, actor_id, location_id)
        basket = await baskets.get_owned(basket_id, actor_id, lock=True)
        if basket.location_id != location_id:
            raise ValidationError("The basket belongs to a different showroom")
        return baskets, basket

    async def _prune_baskets(self, now: datetime.datetime) -> None:
        from app.services.till_basket import TillBasketService

        await TillBasketService(self.db).prune(now)

    async def _validate_cart(
        self, data: HeldSaleCreate
    ) -> tuple[Optional[Customer], dict[uuid.UUID, Sku]]:
        # Acquire SKU locks ordered by ID before any pick locks, as checkout does.
        skus = await self.crud.skus([line.sku_id for line in data.lines])
        customer = await self.crud.customer(data.customer_id)
        if data.customer_id is not None and customer is None:
            raise NotFoundError("Customer not found")
        if customer is not None:
            assert_customer_active(customer)
        pick_ids = set(data.linked_pick_ids.values())
        if data.pick_id is not None:
            pick_ids.add(data.pick_id)
        picks = await self.crud.picks(pick_ids)
        if len(picks) != len(pick_ids):
            raise NotFoundError("Till pick not found")
        if any(
            pick.source_type != PickSourceType.TILL or pick.kit_sku_id not in skus
            for pick in picks.values()
        ):
            raise ValidationError("Referenced picks must be till picks for kits in this basket")
        if any(
            picks[pick_id].kit_sku_id != sku_id for sku_id, pick_id in data.linked_pick_ids.items()
        ):
            raise ValidationError("A linked till pick does not belong to its basket line")
        for line in data.lines:
            sku = skus.get(line.sku_id)
            if sku is None:
                raise NotFoundError("SKU not found")
            if sku.is_archived and sku.is_sellable:
                pick_id = data.linked_pick_ids.get(sku.id, data.pick_id)
                pick = picks.get(pick_id) if pick_id is not None else None
                if self._is_archived_commitment(sku, pick, line.qty, customer):
                    continue
            assert_sku_sellable(sku)
        return customer, skus

    @staticmethod
    def _is_archived_commitment(
        sku: Sku, pick: Optional[Pick], qty: int, customer: Optional[Customer]
    ) -> bool:
        return (
            pick is not None
            and pick.kit_sku_id == sku.id
            and pick.kit_qty == qty
            and pick.invoice_id is None
            and pick.status in _PICK_COMMITMENT_STATUSES
            and sku.archived_at is not None
            and pick.created_at <= sku.archived_at
            and (
                pick.customer_id is None
                or (customer is not None and pick.customer_id == customer.id)
            )
        )

    async def _showroom(self, location_id: uuid.UUID, *, lock: bool = False) -> Location:
        showroom = await self.crud.showroom(location_id, lock=lock)
        if showroom is None:
            raise NotFoundError("Showroom not found")
        return showroom

    @staticmethod
    def _require_active(showroom: Location) -> None:
        if showroom.is_archived:
            raise ConflictError("Held sales require an active showroom")

    @staticmethod
    def _require_matching_request(operation: HeldSaleOperation, fingerprint: str) -> None:
        if operation.request_hash != fingerprint:
            raise ConflictError(
                "This held-sale operation ID was already used with different details"
            )

    def _record_operation(
        self,
        location_id: uuid.UUID,
        actor_id: uuid.UUID,
        action: str,
        operation_id: uuid.UUID,
        fingerprint: str,
        held_sale_id: uuid.UUID,
        now: datetime.datetime,
        *,
        held_current_id: Optional[uuid.UUID] = None,
    ) -> None:
        self.crud.add(
            HeldSaleOperation(
                location_id=location_id,
                actor_id=actor_id,
                action=action,
                operation_id=operation_id,
                request_hash=fingerprint,
                held_sale_id=held_sale_id,
                held_current_id=held_current_id,
                expires_at=now + _RECEIPT_TTL,
            )
        )

    @staticmethod
    def _response(row: HeldSaleRow) -> HeldSale:
        return HeldSale(
            id=row.id,
            reference=f"HS-{row.id.hex[:12].upper()}",
            location_id=row.location_id,
            customer_id=row.customer_id,
            customer_name=row.customer_name,
            held_by_name=row.held_by_name,
            held_at=row.held_at,
            version=row.version,
            note=row.note,
            estimated_total_inc_vat=row.estimated_total_inc_vat,
            pick_id=row.pick_id,
            linked_pick_ids=row.linked_pick_ids,
            lines=row.lines,
        )
