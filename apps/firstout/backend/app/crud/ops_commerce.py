from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
import uuid
from typing import Optional

from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.inventory import LocationStock
from app.models.ops_commerce_acknowledgement import OpsCommerceAcknowledgement
from app.models.product_group import ProductGroup, ProductGroupVariant
from app.models.sku import Sku
from app.crud.stock_reservation import StockReservationCRUD
from app.models.stock_reservation import StockReservation as Reservation
from app.models.stock_reservation_change import StockReservationChange
from app.models.team import Team


def _utc(value: datetime) -> datetime:
    # Naive timestamps are UTC, as the service's revision formatter already assumes.
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


@dataclass(frozen=True)
class PublishedSkuSnapshot:
    id: uuid.UUID
    sku: str
    name: str
    retail_ex_vat: Decimal
    available_quantity: int
    revision: datetime
    observed_at: datetime
    product_group_id: Optional[uuid.UUID]
    product_title: Optional[str]
    options: dict[str, str]
    acknowledged_commitment_ids: list[str]
    made_to_order_offer: Optional[dict[str, object]]


class OpsCommerceCRUD:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def has_company(self, company_id: uuid.UUID) -> bool:
        return (
            await self.db.execute(
                select(Team.id).where(Team.id == company_id, Team.status == "active")
            )
        ).scalar_one_or_none() is not None

    async def published_products(self) -> list[PublishedSkuSnapshot]:
        member = aliased(Sku)
        mapped = aliased(ProductGroupVariant)
        incomplete_group = exists(
            select(mapped.id)
            .join(member, member.id == mapped.source_sku_id)
            .where(
                mapped.product_group_id == ProductGroup.id,
                (
                    member.is_archived.is_(True)
                    | member.storefront_published.is_(False)
                    | member.is_sellable.is_(False)
                    | (member.retail_ex_vat <= 0)
                    | member.retail_ex_vat.is_(None)
                ),
            )
        )
        result = await self.db.execute(
            select(
                Sku.id,
                Sku.our_ref,
                Sku.name,
                Sku.retail_ex_vat,
                # The public shop sells whole items from individual locations.
                func.coalesce(func.sum(func.floor(func.greatest(LocationStock.on_hand, 0))), 0),
                func.greatest(
                    Sku.updated_at,
                    func.coalesce(func.max(LocationStock.updated_at), Sku.updated_at),
                    func.coalesce(ProductGroup.updated_at, Sku.updated_at),
                    func.coalesce(ProductGroupVariant.updated_at, Sku.updated_at),
                ),
                func.clock_timestamp(),
                ProductGroup.id,
                ProductGroup.title,
                ProductGroupVariant.options,
                Sku.made_to_order_capacity,
                Sku.made_to_order_lead_time_min_days,
                Sku.made_to_order_lead_time_max_days,
                Sku.made_to_order_expires_at,
                Sku.made_to_order_offer_id,
            )
            .outerjoin(LocationStock, LocationStock.sku_id == Sku.id)
            .outerjoin(ProductGroupVariant, ProductGroupVariant.source_sku_id == Sku.id)
            .outerjoin(ProductGroup, ProductGroup.id == ProductGroupVariant.product_group_id)
            .where(
                Sku.storefront_published.is_(True),
                Sku.is_archived.is_(False),
                Sku.is_sellable.is_(True),
                Sku.retail_ex_vat > 0,
                (
                    ProductGroupVariant.id.is_(None)
                    | (ProductGroup.storefront_published.is_(True) & ~incomplete_group)
                ),
            )
            .group_by(Sku.id, ProductGroup.id, ProductGroupVariant.id)
            .order_by(Sku.our_ref)
        )
        rows = result.all()
        acknowledgements: dict[uuid.UUID, list[str]] = {}
        acknowledgement_revisions: dict[uuid.UUID, datetime] = {}
        if rows:
            acknowledgement_result = await self.db.execute(
                select(
                    OpsCommerceAcknowledgement.source_sku_id,
                    OpsCommerceAcknowledgement.commitment_id,
                    OpsCommerceAcknowledgement.updated_at,
                )
                .where(OpsCommerceAcknowledgement.source_sku_id.in_([row[0] for row in rows]))
                .order_by(OpsCommerceAcknowledgement.commitment_id)
            )
            for sku_id, commitment_id, updated_at in acknowledgement_result.all():
                acknowledgements.setdefault(sku_id, []).append(commitment_id)
                previous = acknowledgement_revisions.get(sku_id)
                if previous is None or updated_at > previous:
                    acknowledgement_revisions[sku_id] = updated_at
        # Live till reservations (any holder) are promised stock; expired ones are ignored.
        now = datetime.now(timezone.utc)
        sku_ids = [row[0] for row in rows]
        reserved = (
            await StockReservationCRUD(self.db).reserved_by_others(now, None, sku_ids)
            if rows
            else {}
        )
        # A reservation change (create, release, move, prune) is marked by a database trigger;
        # lazy expiry changes nothing, so an unpruned expired row counts from its expiry.
        reservation_revisions: dict[uuid.UUID, datetime] = {}
        if rows:
            changed = await self.db.execute(
                select(StockReservationChange.sku_id, StockReservationChange.changed_at).where(
                    StockReservationChange.sku_id.in_(sku_ids)
                )
            )
            reservation_revisions.update(changed.all())
            expired = await self.db.execute(
                select(Reservation.sku_id, func.max(Reservation.expires_at))
                .where(Reservation.sku_id.in_(sku_ids), Reservation.expires_at <= now)
                .group_by(Reservation.sku_id)
            )
            for sku_id, expires_at in expired.all():
                if (
                    sku_id not in reservation_revisions
                    or expires_at > reservation_revisions[sku_id]
                ):
                    reservation_revisions[sku_id] = expires_at
        return [
            PublishedSkuSnapshot(
                id=row[0],
                sku=row[1],
                name=row[2],
                retail_ex_vat=row[3],
                available_quantity=max(0, int(max(0, row[4])) - reserved.get(row[0], 0)),
                revision=max(
                    _utc(row[5]),
                    _utc(acknowledgement_revisions.get(row[0], row[5])),
                    _utc(reservation_revisions.get(row[0], row[5])),
                ),
                observed_at=row[6],
                product_group_id=row[7],
                product_title=row[8],
                options=row[9] or {},
                acknowledged_commitment_ids=acknowledgements.get(row[0], []),
                made_to_order_offer=(
                    {
                        "id": row[14],
                        "capacity": row[10],
                        "min_lead_time_days": row[11],
                        "max_lead_time_days": row[12],
                        "expires_at": row[13],
                    }
                    if row[14] is not None
                    else None
                ),
            )
            for row in rows
        ]
