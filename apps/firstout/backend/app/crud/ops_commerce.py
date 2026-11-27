from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
import uuid
from typing import Optional

from sqlalchemy import ColumnElement, exists, false, func, select, true
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.catalogue_list import SkuCategory
from app.models.inventory import LocationStock
from app.models.ops_commerce_acknowledgement import OpsCommerceAcknowledgement
from app.models.product_group import ProductGroup, ProductGroupVariant
from app.models.sku import Sku
from app.crud.stock_reservation import StockReservationCRUD
from app.models.stock_reservation import StockReservation as Reservation
from app.models.stock_reservation_change import StockReservationChange
from f0rge_db.organisation import tenant_id_ctx
from app.models.team import Team


# Owner decision, 21 Nov 2026: Firstout SKU category (trimmed, any case) -> shop category handle.
# Since migration 120 the feed reads the section from the SKU's category row
# (``sku_categories.shop_category``); this map is the list of valid section slugs (its
# values) and what new categories with these names start with.
SHOP_CATEGORIES = {
    "sofas": "sofas-armchairs",
    "armchairs": "sofas-armchairs",
    "dining room": "dining-room",
    "bedroom": "bedroom",
    "coffee and lamp tables": "coffee-console-tables",
    "consoles and tv units": "coffee-console-tables",
}


# The only shop-section source: the feed selects and labels rows with this one SQL
# expression, the shop section of the SKU's (top-level) category row. A rename keeps it.
SHOP_CATEGORY = (
    select(SkuCategory.shop_category)
    .where(SkuCategory.id == Sku.category_id, SkuCategory.team_id == Sku.team_id)
    .scalar_subquery()
)

# The auto-publish rule, per SKU: a shop category, a Firstout photo, and not hidden.
ON_SHOP = (
    SHOP_CATEGORY.is_not(None)
    & Sku.photo_storage_key.is_not(None)
    & Sku.storefront_hidden.is_(False)
)


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
    photo_storage_key: Optional[str]
    shop_category: Optional[str]
    gallery_photo_keys: tuple[str, ...]
    dimensions_cm: dict[str, Optional[Decimal]]
    piece_count: Optional[int]
    setting_photo_storage_key: Optional[str]
    detail_photo_storage_key: Optional[str]
    swatch_hex: Optional[str]
    second_detail_photo_storage_key: Optional[str]
    sell_multiple: int
    min_sell_qty: int


class OpsCommerceCRUD:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def has_company(self, company_id: uuid.UUID) -> bool:
        return (
            await self.db.execute(
                select(Team.id).where(Team.id == company_id, Team.status == "active")
            )
        ).scalar_one_or_none() is not None

    async def curated_catalogue_enabled(self, company_id: uuid.UUID) -> bool:
        # Keep this mode and the feed rows on the same side of a concurrent activation.
        return bool(
            await self.db.scalar(
                select(Team.storefront_curated_catalogue)
                .where(Team.id == company_id)
                .with_for_update(read=True)
            )
        )

    async def published_products(
        self,
        *,
        auto_publish: bool = False,
        curated: bool = False,
        source_sku_id: Optional[uuid.UUID] = None,
    ) -> list[PublishedSkuSnapshot]:
        member = aliased(Sku)
        mapped = aliased(ProductGroupVariant)
        selected = Sku.storefront_published.is_(True)
        group_selected: ColumnElement[bool] = ProductGroup.storefront_published.is_(True)
        member_unselected: ColumnElement[bool] = member.storefront_published.is_(False)
        if curated:
            selected = (
                Sku.storefront_catalogue_selected.is_(True)
                & Sku.storefront_hidden.is_(False)
                & SHOP_CATEGORY.is_not(None)
            )
            group_selected = true()
            member_unselected = false()
        elif auto_publish:
            # Every row, grouped or not, meets the rule itself; a group shows with the members
            # that do. Archived, unsellable or unpriced members still keep the whole group off.
            selected = ON_SHOP
            group_selected = true()
            member_unselected = false()
        incomplete_group = exists(
            select(mapped.id)
            .join(member, member.id == mapped.source_sku_id)
            .where(
                mapped.product_group_id == ProductGroup.id,
                member.storefront_catalogue_selected.is_(True) if curated else true(),
                (
                    member.is_archived.is_(True)
                    | member_unselected
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
                Sku.photo_storage_key,
                SHOP_CATEGORY,
                Sku.gallery_photo_keys,
                Sku.width_cm,
                Sku.depth_cm,
                Sku.height_cm,
                Sku.diameter_cm,
                Sku.piece_count,
                Sku.setting_photo_storage_key,
                Sku.detail_photo_storage_key,
                Sku.swatch_hex,
                Sku.second_detail_photo_storage_key,
                Sku.sell_multiple,
                Sku.min_sell_qty,
            )
            .outerjoin(LocationStock, LocationStock.sku_id == Sku.id)
            .outerjoin(ProductGroupVariant, ProductGroupVariant.source_sku_id == Sku.id)
            .outerjoin(ProductGroup, ProductGroup.id == ProductGroupVariant.product_group_id)
            .where(
                selected,
                Sku.is_archived.is_(False),
                Sku.is_sellable.is_(True),
                Sku.retail_ex_vat > 0,
                Sku.id == source_sku_id if source_sku_id is not None else true(),
                ProductGroupVariant.id.is_(None) | (group_selected & ~incomplete_group),
            )
            .group_by(Sku.id, ProductGroup.id, ProductGroupVariant.id)
            .order_by(Sku.our_ref)
        )
        rows = result.all()
        # Members whose categories map to different shop categories take the first member's
        # (by SKU code), so every variant of one product carries the same shop category.
        group_categories: dict[uuid.UUID, str] = {}
        if auto_publish or curated:
            for row in rows:
                if row[7] is not None:
                    group_categories.setdefault(row[7], row[16])
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
                    StockReservationChange.team_id == tenant_id_ctx.get(),
                    StockReservationChange.sku_id.in_(sku_ids),
                )
            )
            reservation_revisions.update(changed.all())
            expired = await self.db.execute(
                select(Reservation.sku_id, func.max(Reservation.expires_at))
                .where(
                    Reservation.team_id == tenant_id_ctx.get(),
                    Reservation.sku_id.in_(sku_ids),
                    Reservation.expires_at <= now,
                )
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
                photo_storage_key=row[17][0] if row[17] else row[15],
                shop_category=(
                    (group_categories[row[7]] if row[7] is not None else row[16])
                    if auto_publish or curated
                    else None
                ),
                gallery_photo_keys=tuple(row[17] or ()),
                dimensions_cm={
                    "width": row[18],
                    "depth": row[19],
                    "height": row[20],
                    "diameter": row[21],
                },
                piece_count=row[22],
                setting_photo_storage_key=row[23],
                detail_photo_storage_key=row[24],
                swatch_hex=row[25],
                second_detail_photo_storage_key=row[26],
                sell_multiple=row[27],
                min_sell_qty=row[28],
            )
            for row in rows
        ]
