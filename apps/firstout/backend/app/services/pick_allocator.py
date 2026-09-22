from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Optional, Sequence


LOCATION_TYPE_WAREHOUSE = "warehouse"
LOCATION_TYPE_SHOWROOM = "showroom"


@dataclass(frozen=True)
class ComponentNeed:
    sku_id: uuid.UUID
    qty_needed: int


@dataclass(frozen=True)
class LocationStockRow:
    location_id: uuid.UUID
    sku_id: uuid.UUID
    on_hand: int
    location_type: str
    location_name: str
    is_archived: bool


@dataclass(frozen=True)
class SuggestedAllocation:
    sku_id: uuid.UUID
    location_id: uuid.UUID
    qty: int


@dataclass(frozen=True)
class LineAllocation:
    sku_id: uuid.UUID
    qty_needed: int
    qty_allocated: int
    qty_short: int
    allocations: list[SuggestedAllocation]


@dataclass(frozen=True)
class AllocationResult:
    lines: list[LineAllocation]
    needs_confirm: bool


@dataclass(frozen=True)
class LocationMeta:
    location_id: uuid.UUID
    location_type: str
    location_name: str
    is_archived: bool


def walk_order(
    locations: Sequence[LocationMeta],
    pick_priority: Sequence[uuid.UUID],
    always_prefer_warehouse: bool,
) -> list[uuid.UUID]:
    active = {loc.location_id: loc for loc in locations if not loc.is_archived}
    if pick_priority:
        ordered = [lid for lid in pick_priority if lid in active]
    else:
        warehouses = sorted(
            [loc for loc in active.values() if loc.location_type == LOCATION_TYPE_WAREHOUSE],
            key=lambda loc: loc.location_name.lower(),
        )
        showrooms = sorted(
            [loc for loc in active.values() if loc.location_type == LOCATION_TYPE_SHOWROOM],
            key=lambda loc: loc.location_name.lower(),
        )
        others = sorted(
            [
                loc
                for loc in active.values()
                if loc.location_type not in (LOCATION_TYPE_WAREHOUSE, LOCATION_TYPE_SHOWROOM)
            ],
            key=lambda loc: loc.location_name.lower(),
        )
        ordered = [loc.location_id for loc in warehouses + showrooms + others]
    if always_prefer_warehouse:
        warehouses = [
            lid for lid in ordered if active[lid].location_type == LOCATION_TYPE_WAREHOUSE
        ]
        rest = [lid for lid in ordered if active[lid].location_type != LOCATION_TYPE_WAREHOUSE]
        ordered = warehouses + rest
    return ordered


def first_warehouse_id(
    locations: Sequence[LocationMeta],
    pick_priority: Sequence[uuid.UUID],
    always_prefer_warehouse: bool,
) -> Optional[uuid.UUID]:
    metas = {loc.location_id: loc for loc in locations}
    for lid in walk_order(locations, pick_priority, always_prefer_warehouse):
        if metas[lid].location_type == LOCATION_TYPE_WAREHOUSE:
            return lid
    return None


def allocations_need_confirm(
    needs: Sequence[ComponentNeed],
    stocks: Sequence[LocationStockRow],
    allocations: Sequence[SuggestedAllocation],
) -> bool:
    warehouse_ids = {
        row.location_id
        for row in stocks
        if row.location_type == LOCATION_TYPE_WAREHOUSE and not row.is_archived
    }
    on_hand: dict[tuple[uuid.UUID, uuid.UUID], int] = {}
    for row in stocks:
        if row.is_archived:
            continue
        key = (row.sku_id, row.location_id)
        on_hand[key] = on_hand.get(key, 0) + max(row.on_hand, 0)

    for need in needs:
        warehouse_qty = sum(on_hand.get((need.sku_id, lid), 0) for lid in warehouse_ids)
        warehouse_alloc = sum(
            item.qty
            for item in allocations
            if item.sku_id == need.sku_id and item.location_id in warehouse_ids
        )
        non_warehouse_alloc = sum(
            item.qty
            for item in allocations
            if item.sku_id == need.sku_id and item.location_id not in warehouse_ids
        )
        if non_warehouse_alloc <= 0:
            continue
        leftover = warehouse_qty - warehouse_alloc
        if leftover > 0:
            return True
        if warehouse_qty < need.qty_needed:
            return True
    return False


def allocate(
    needs: Sequence[ComponentNeed],
    stocks: Sequence[LocationStockRow],
    always_prefer_warehouse: bool,
    pick_priority: Sequence[uuid.UUID],
) -> AllocationResult:
    metas: dict[uuid.UUID, LocationMeta] = {}
    remaining: dict[tuple[uuid.UUID, uuid.UUID], int] = {}
    for row in stocks:
        metas[row.location_id] = LocationMeta(
            location_id=row.location_id,
            location_type=row.location_type,
            location_name=row.location_name,
            is_archived=row.is_archived,
        )
        if row.is_archived:
            continue
        key = (row.sku_id, row.location_id)
        remaining[key] = remaining.get(key, 0) + max(row.on_hand, 0)

    order = walk_order(list(metas.values()), pick_priority, always_prefer_warehouse)
    lines: list[LineAllocation] = []
    suggested: list[SuggestedAllocation] = []
    for need in needs:
        left = need.qty_needed
        line_allocs: list[SuggestedAllocation] = []
        for location_id in order:
            available = remaining.get((need.sku_id, location_id), 0)
            if available <= 0:
                continue
            take = available if available < left else left
            if take <= 0:
                continue
            alloc = SuggestedAllocation(
                sku_id=need.sku_id,
                location_id=location_id,
                qty=take,
            )
            line_allocs.append(alloc)
            remaining[(need.sku_id, location_id)] = available - take
            left -= take
            if left == 0:
                break
        allocated = need.qty_needed - left
        lines.append(
            LineAllocation(
                sku_id=need.sku_id,
                qty_needed=need.qty_needed,
                qty_allocated=allocated,
                qty_short=left,
                allocations=line_allocs,
            )
        )
        suggested.extend(line_allocs)

    return AllocationResult(
        lines=lines,
        needs_confirm=allocations_need_confirm(needs, stocks, suggested),
    )
