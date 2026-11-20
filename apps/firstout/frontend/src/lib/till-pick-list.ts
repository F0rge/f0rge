import type { PickAllocation, PickDefaultAllocations, PickLine, UpdatePickPayload } from "./picks";
import { formatQuantity } from "./quantity";

type Alloc = { location_id: string; qty: number };

/** Allocations that take stock; GET /picks/{id} also lists every stocked location at qty 0. */
export function sources(line: PickLine): PickAllocation[] {
  return line.allocations.filter((cell) => cell.qty > 0);
}

const allocKey = (allocs: Alloc[]) =>
  allocs.filter((a) => a.qty > 0).map((a) => `${a.location_id}:${a.qty}`).sort().join("|");

/** Default allocations for one line ([] when the allocator found nothing or defaults are unknown). */
export function lineDefaults(defaults: PickDefaultAllocations | null, skuId: string) {
  return defaults?.lines.find((line) => line.sku_id === skuId)?.allocations ?? [];
}

/** A line differs from what the allocator would choose now. Unknown defaults never read as changed. */
export function isLineChanged(line: PickLine, defaults: PickDefaultAllocations | null): boolean {
  if (!defaults) return false;
  return allocKey(sources(line)) !== allocKey(lineDefaults(defaults, line.sku_id));
}

/** PATCH body: every line keeps its allocations, except `skuId`, which takes all of its qty from `locationId`. */
export function sourcePatch(lines: PickLine[], skuId: string, locationId: string): UpdatePickPayload {
  return {
    lines: lines.map((line) => ({
      sku_id: line.sku_id,
      allocations: line.sku_id === skuId
        ? [{ location_id: locationId, qty: line.qty_needed }]
        : sources(line).map(({ location_id, qty }) => ({ location_id, qty })),
    })),
  };
}

/** PATCH body that puts every line back on the allocator's default. */
export function defaultsPatch(lines: PickLine[], defaults: PickDefaultAllocations): UpdatePickPayload {
  return {
    lines: lines.map((line) => ({
      sku_id: line.sku_id,
      allocations: lineDefaults(defaults, line.sku_id).map(({ location_id, qty }) => ({ location_id, qty })),
    })),
  };
}

/** One source-menu option: "Warehouse · 4 on hand · default". The default comes from the server's allocator. */
export function sourceOptionText(
  cell: PickAllocation,
  opts: { isDefault: boolean; isShowroom: boolean },
): string {
  const parts = [cell.location_name, `${formatQuantity(cell.on_hand)} on hand`];
  if (opts.isDefault) parts.push("default");
  if (opts.isShowroom) parts.push("this showroom");
  return parts.join(" · ");
}

const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? "" : "s"}`;

export function confirmedTitle(pickNumber: string, lines: PickLine[]): string {
  const places = new Set(lines.flatMap((line) => sources(line).map((cell) => cell.location_id)));
  return `Pick ${pickNumber} confirmed · ${plural(lines.length, "line")} from ${plural(places.size, "location")}`;
}

export type NextStep = { locationId: string; heading: string; detail: string };

/** "What happens next", one entry per source location in first-seen order. */
export function whatHappensNext(
  lines: PickLine[],
  locationTypes: Map<string, string>,
  showroomId: string,
): NextStep[] {
  const groups = new Map<string, { name: string; items: string[] }>();
  for (const line of lines) {
    for (const cell of sources(line)) {
      const group = groups.get(cell.location_id) ?? { name: cell.location_name, items: [] };
      group.items.push(`${line.sku_name || line.sku_our_ref} ×${formatQuantity(cell.qty)}`);
      groups.set(cell.location_id, group);
    }
  }
  return [...groups].map(([locationId, { name, items }]) => ({
    locationId,
    heading: `${name} — ${items.join(", ")}`,
    detail: locationTypes.get(locationId) === "warehouse"
      ? `picked at ${name}, then staged`
      : `staged for collection or delivery from ${locationId === showroomId ? "here" : name}`,
  }));
}

/** The quiet note for sale lines that need no stock, e.g. "DELIVERY JHB (S001) needs no stock, …". */
export function noStockNote(labels: string[]): string | null {
  if (!labels.length) return null;
  const names = labels.length === 1
    ? labels[0]
    : `${labels.slice(0, -1).join(", ")} and ${labels[labels.length - 1]}`;
  return labels.length === 1
    ? `${names} needs no stock, so it is not on the pick list.`
    : `${names} need no stock, so they are not on the pick list.`;
}
