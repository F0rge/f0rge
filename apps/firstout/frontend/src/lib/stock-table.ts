import type { InventorySku, Location } from "@/lib/api";

export type StockPipelineChip = "on_water" | "at_warehouse" | "at_showroom";

export function formatStockQty(value: number): string {
  return value > 0 ? String(value) : "—";
}

export function activeLocations(locations: Location[]): Location[] {
  return locations.filter((location) => !location.is_archived);
}

export function showroomLocation(locations: Location[]): Location | undefined {
  const active = activeLocations(locations);
  const bedfordview = active.find((location) => location.name === "Bedfordview");
  if (bedfordview?.type === "showroom") {
    return bedfordview;
  }
  return active.find((location) => location.type === "showroom");
}

export function locationOnHand(entry: InventorySku, locationId: string): number {
  const match = entry.locations.find((location) => location.location_id === locationId);
  return match?.on_hand ?? 0;
}

export function showroomAvailable(entry: InventorySku, showroom: Location | undefined): number {
  if (!showroom) {
    return 0;
  }
  return locationOnHand(entry, showroom.id);
}

export function matchesPipelineChip(
  entry: InventorySku,
  chip: StockPipelineChip,
  locations: Location[],
): boolean {
  if (chip === "on_water") {
    return entry.on_order > 0;
  }
  const active = activeLocations(locations);
  if (chip === "at_warehouse") {
    return active
      .filter((location) => location.type === "warehouse")
      .some((location) => locationOnHand(entry, location.id) > 0);
  }
  return active
    .filter((location) => location.type === "showroom")
    .some((location) => locationOnHand(entry, location.id) > 0);
}

export function matchesPipelineChips(
  entry: InventorySku,
  chips: StockPipelineChip[],
  locations: Location[],
): boolean {
  if (chips.length === 0) {
    return true;
  }
  return chips.some((chip) => matchesPipelineChip(entry, chip, locations));
}

export function matchesStockSearch(entry: InventorySku, query: string): boolean {
  const normalized = query.trim().toLowerCase();
  if (!normalized) {
    return true;
  }
  return (
    entry.our_ref.toLowerCase().includes(normalized) ||
    entry.name.toLowerCase().includes(normalized)
  );
}

export function visibleBins(
  bins: InventorySku["locations"][number]["bins"] | undefined,
): InventorySku["locations"][number]["bins"] {
  const nonzero = (bins ?? []).filter((bin) => bin.on_hand > 0);
  if (nonzero.length <= 1) {
    return [];
  }
  return nonzero;
}
